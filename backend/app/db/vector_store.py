"""Операции над векторным хранилищем Qdrant.

Сигнатуры публичных функций сохранены совместимыми с прежней версией (pgvector),
чтобы не трогать LLM-клиенты. Метаданные документов хранятся в Postgres,
векторы и тексты чанков — в Qdrant.
"""
import uuid
from dataclasses import dataclass

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import KnowledgeDocument
from app.db.qdrant_client import get_qdrant

settings = get_settings()


@dataclass
class SearchResult:
    """Один найденный релевантный фрагмент из базы знаний.

    Контракт для LLM-клиентов — поля не менять без правок во всех клиентах.
    """

    chunk_id: str
    document_id: int
    document_title: str
    doc_type: str
    text: str
    article_ref: str | None
    similarity: float  # косинусное сходство 0..1


# ------------------------------------------------------------
#  Метаданные документов (Postgres)
# ------------------------------------------------------------

async def create_document(
    session: AsyncSession,
    *,
    title: str,
    doc_type: str = "other",
    source_url: str | None = None,
    file_name: str | None = None,
) -> KnowledgeDocument:
    """Создать запись источника права в Postgres."""
    doc = KnowledgeDocument(
        title=title,
        doc_type=doc_type,
        source_url=source_url,
        file_name=file_name,
    )
    session.add(doc)
    await session.flush()
    return doc


async def list_documents(session: AsyncSession) -> list[KnowledgeDocument]:
    """Список всех источников права (метаданные из Postgres)."""
    from sqlalchemy import select

    stmt = select(KnowledgeDocument).order_by(KnowledgeDocument.created_at.desc())
    return list((await session.execute(stmt)).scalars())


async def delete_document(session: AsyncSession, document_id: int) -> bool:
    """Удалить источник: метаданные из Postgres + все чанки из Qdrant."""
    doc = await session.get(KnowledgeDocument, document_id)
    if doc is None:
        return False

    # Удаляем чанки из Qdrant по фильтру document_id
    qdrant = get_qdrant().client
    from qdrant_client.http.models import FieldCondition, MatchValue, Filter

    qdrant.delete(
        collection_name=settings.qdrant_collection,
        points_selector=Filter(
            must=[
                FieldCondition(
                    key="document_id",
                    match=MatchValue(value=document_id),
                )
            ]
        ),
    )
    logger.info("Чанки документа {} удалены из Qdrant", document_id)

    # Удаляем метаданные из Postgres
    await session.delete(doc)
    return True


# ------------------------------------------------------------
#  Чанки (Qdrant)
# ------------------------------------------------------------

async def add_chunks(
    session: AsyncSession,
    *,
    document_id: int,
    chunks: list[dict],
    metadata: dict | None = None,
) -> int:
    """Сохранить чанки с эмбеддингами в Qdrant.

    Каждый элемент chunks — словарь с ключами:
        text, embedding (list[float]), article_ref (str|None)
    metadata — общие метаданные документа (year, court_level, doc_type, ...)
    Возвращает количество сохранённых чанков.
    """
    if not chunks:
        await _update_chunk_count(session, document_id, 0)
        return 0

    from qdrant_client.http.models import PointStruct

    qdrant = get_qdrant().client
    doc_meta = metadata or {}

    points = []
    for i, item in enumerate(chunks):
        payload = {
            "document_id": document_id,
            "text": item["text"],
            "article_ref": item.get("article_ref"),
            "chunk_index": i,
            # Метаданные документа (могут быть None для законов)
            "doc_type": doc_meta.get("doc_type", "other"),
            "year": doc_meta.get("year"),
            "court_level": doc_meta.get("court_level"),
            "case_number": doc_meta.get("case_number"),
            "source_title": doc_meta.get("source_title"),
        }
        points.append(
            PointStruct(
                id=str(uuid.uuid4()),
                vector=item["embedding"],
                payload=payload,
            )
        )

    qdrant.upsert(
        collection_name=settings.qdrant_collection,
        points=points,
    )
    logger.info(
        "Сохранено {} чанков в Qdrant для документа id={} (year={}, court={})",
        len(points),
        document_id,
        doc_meta.get("year"),
        doc_meta.get("court_level"),
    )

    await _update_chunk_count(session, document_id, len(points))
    return len(points)


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
    year_from: int | None = None,
    year_to: int | None = None,
    court_level: str | None = None,
    doc_type: str | None = None,
) -> list[SearchResult]:
    """Найти top_k наиболее похожих чанков в Qdrant.

    Поддерживает опциональную фильтрацию по году, типу суда и типу документа.
    Метаданные документа (title) подтягиваются из Postgres для отображения.
    """
    from qdrant_client.http.models import (
        FieldCondition,
        Filter,
        MatchValue,
        Range,
    )

    qdrant = get_qdrant().client

    # Собираем фильтр
    conditions = []
    if year_from is not None or year_to is not None:
        conditions.append(
            FieldCondition(
                key="year",
                range=Range(gte=year_from, lte=year_to),
            )
        )
    if court_level:
        conditions.append(
            FieldCondition(
                key="court_level",
                match=MatchValue(value=court_level),
            )
        )
    if doc_type:
        conditions.append(
            FieldCondition(
                key="doc_type",
                match=MatchValue(value=doc_type),
            )
        )

    query_filter = Filter(must=conditions) if conditions else None

    results = qdrant.query_points(
        collection_name=settings.qdrant_collection,
        query=query_embedding,
        query_filter=query_filter,
        limit=top_k,
        with_payload=True,
    )

    # Собираем mapping document_id → title из Postgres (одним запросом)
    doc_ids = {
        point.payload.get("document_id")
        for point in results.points
        if point.payload and point.payload.get("document_id")
    }
    titles_map = await _fetch_doc_titles(session, doc_ids)

    search_results: list[SearchResult] = []
    for point in results.points:
        if not point.payload:
            continue
        similarity = float(point.score or 0.0)
        if similarity < min_similarity:
            continue
        doc_id = point.payload.get("document_id", 0)
        search_results.append(
            SearchResult(
                chunk_id=str(point.id),
                document_id=doc_id,
                document_title=titles_map.get(doc_id, "Неизвестно"),
                doc_type=point.payload.get("doc_type", "other"),
                text=point.payload.get("text", ""),
                article_ref=point.payload.get("article_ref"),
                similarity=similarity,
            )
        )
    return search_results


async def _fetch_doc_titles(
    session: AsyncSession, doc_ids: set[int]
) -> dict[int, str]:
    """Получить mapping {document_id: title} одним запросом к Postgres."""
    if not doc_ids:
        return {}
    from sqlalchemy import select

    stmt = select(KnowledgeDocument.id, KnowledgeDocument.title).where(
        KnowledgeDocument.id.in_(doc_ids)
    )
    rows = (await session.execute(stmt)).all()
    return {row.id: row.title for row in rows}


async def count_chunks() -> int:
    """Общее количество чанков в коллекции Qdrant."""
    qdrant = get_qdrant().client
    info = qdrant.count(
        collection_name=settings.qdrant_collection, exact=True
    )
    return info.count
