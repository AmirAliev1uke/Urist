"""Операции над pgvector: сохранение чанков и поиск ближайших по сходству."""
from dataclasses import dataclass

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DocumentChunk, KnowledgeDocument


@dataclass
class SearchResult:
    """Один найденный релевантный фрагмент из базы знаний."""

    chunk_id: int
    document_id: int
    document_title: str
    doc_type: str
    text: str
    article_ref: str | None
    similarity: float  # косинусное сходство 0..1


async def create_document(
    session: AsyncSession,
    *,
    title: str,
    doc_type: str = "other",
    source_url: str | None = None,
    file_name: str | None = None,
) -> KnowledgeDocument:
    """Создать запись источника права."""
    doc = KnowledgeDocument(
        title=title,
        doc_type=doc_type,
        source_url=source_url,
        file_name=file_name,
    )
    session.add(doc)
    await session.flush()
    return doc


async def add_chunks(
    session: AsyncSession,
    *,
    document_id: int,
    chunks: list[dict],
) -> int:
    """Сохранить чанки с эмбеддингами.

    Каждый элемент chunks — словарь с ключами:
        text, embedding (list[float]), article_ref (str|None), metadata (dict)
    Возвращает количество сохранённых чанков.
    """
    if not chunks:
        await _update_chunk_count(session, document_id, 0)
        return 0

    objects = [
        DocumentChunk(
            document_id=document_id,
            chunk_index=i,
            text=item["text"],
            article_ref=item.get("article_ref"),
            metadata_=item.get("metadata", {}),
            embedding=item["embedding"],
        )
        for i, item in enumerate(chunks)
    ]
    session.add_all(objects)
    await session.flush()
    await _update_chunk_count(session, document_id, len(objects))
    return len(objects)


async def _update_chunk_count(
    session: AsyncSession, document_id: int, count: int
) -> None:
    doc = await session.get(KnowledgeDocument, document_id)
    if doc is not None:
        doc.total_chunks = count


async def similarity_search(
    session: AsyncSession,
    *,
    query_embedding: list[float],
    top_k: int = 8,
    min_similarity: float = 0.0,
) -> list[SearchResult]:
    """Найти top_k наиболее похожих чанков на запрос.

    Использует оператор <=> (cosine distance) из pgvector.
    similarity = 1 - cosine_distance, т.е. чем ближе к 1 — тем релевантнее.
    """
    distance = DocumentChunk.embedding.cosine_distance(query_embedding).label(
        "distance"
    )
    stmt = (
        select(
            DocumentChunk.id,
            DocumentChunk.document_id,
            KnowledgeDocument.title,
            KnowledgeDocument.doc_type,
            DocumentChunk.text,
            DocumentChunk.article_ref,
            distance,
        )
        .join(KnowledgeDocument, DocumentChunk.document_id == KnowledgeDocument.id)
        .order_by(distance)
        .limit(top_k)
    )

    rows = (await session.execute(stmt)).all()
    results: list[SearchResult] = []
    for row in rows:
        similarity = 1.0 - float(row.distance)
        if similarity < min_similarity:
            continue
        results.append(
            SearchResult(
                chunk_id=row.id,
                document_id=row.document_id,
                document_title=row.title,
                doc_type=row.doc_type,
                text=row.text,
                article_ref=row.article_ref,
                similarity=similarity,
            )
        )
    return results


async def list_documents(session: AsyncSession) -> list[KnowledgeDocument]:
    """Список всех источников права в базе знаний."""
    stmt = select(KnowledgeDocument).order_by(KnowledgeDocument.created_at.desc())
    return list((await session.execute(stmt)).scalars())


async def delete_document(session: AsyncSession, document_id: int) -> bool:
    """Удалить источник и все его чанки (каскад). Возвращает True если был."""
    doc = await session.get(KnowledgeDocument, document_id)
    if doc is None:
        return False
    # Чанки удалятся каскадно (ON DELETE CASCADE), но на всякий случай — явно
    await session.execute(
        delete(DocumentChunk).where(DocumentChunk.document_id == document_id)
    )
    await session.delete(doc)
    return True
