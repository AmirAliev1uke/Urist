"""RAG-оркестрация: связывает парсинг, классификацию, embeddings, поиск и LLM.

Два основных сценария:
  - ingest_document: наполнение базы знаний (Поток A, PDF + DOCX + DOC)
    документ → парсинг → авто-классификация → чанкование → embedding → Qdrant
  - analyze_document: анализ документа юриста (Поток B, PDF + DOCX + DOC)
    документ → embedding запроса → поиск в Qdrant → промпт → LLM → отчёт
"""
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.chunker import chunk_document
from app.core.classifier import extract_metadata
from app.core.document_parser import parse_document
from app.core.embeddings import Embedder
from app.core.llm.base import BaseLLMClient
from app.db import vector_store
from app.db.vector_store import SearchResult
from app.schemas.analysis import AnalysisResult


async def ingest_document(
    session: AsyncSession,
    *,
    file_bytes: bytes,
    title: str,
    doc_type: str = "other",
    source_url: str | None = None,
    file_name: str | None = None,
    embedder: Embedder | None = None,
) -> dict:
    """Поток A: распарсить PDF, авто-классифицировать, чанковать, векторизовать.

    Возвращает словарь с метаданными и количеством чанков:
      {chunks, doc_type, year, court_level, case_number}
    """
    embedder = embedder or Embedder()

    logger.info("Ингестия документа «{}» ({} байт)", title, len(file_bytes))
    parsed = parse_document(file_bytes, file_name=file_name or title)
    logger.info(
        "Документ распарсен: формат {}, {} символов",
        parsed.file_type,
        parsed.total_chars,
    )

    # --- Авто-классификация: определяем год, тип суда, тип документа ---
    metadata = extract_metadata(parsed.full_text, file_name or title)
    logger.info(
        "Классификация: doc_type={}, year={}, court={}, case={}",
        metadata.doc_type,
        metadata.year,
        metadata.court_level,
        metadata.case_number,
    )
    # Классификатор может точнее определить doc_type — используем его
    doc_type = metadata.doc_type if metadata.doc_type != "other" else doc_type

    chunks = chunk_document(parsed.full_text)
    logger.info("Получено {} чанков", len(chunks))
    if not chunks:
        raise ValueError("Документ не содержит текста для индексации.")

    texts = [c.text for c in chunks]
    logger.info("Векторизация {} чанков...", len(texts))
    embeddings = embedder.embed_batch(texts)

    payload = [
        {
            "text": c.text,
            "embedding": emb,
            "article_ref": c.article_ref,
        }
        for c, emb in zip(chunks, embeddings, strict=True)
    ]

    # Метаданные документа для Qdrant (year, court_level и т.д.)
    doc_meta = {
        "doc_type": doc_type,
        "year": metadata.year,
        "court_level": metadata.court_level,
        "case_number": metadata.case_number,
        "source_title": title,
    }

    doc = await vector_store.create_document(
        session,
        title=title,
        doc_type=doc_type,
        source_url=source_url,
        file_name=file_name,
    )
    saved = await vector_store.add_chunks(
        session,
        document_id=doc.id,
        chunks=payload,
        metadata=doc_meta,
    )
    await session.commit()
    logger.info(
        "Сохранено {} чанков для документа id={} (year={}, court={})",
        saved,
        doc.id,
        metadata.year,
        metadata.court_level,
    )
    return {
        "chunks": saved,
        "doc_type": doc_type,
        "year": metadata.year,
        "court_level": metadata.court_level,
        "case_number": metadata.case_number,
        "document_id": doc.id,
    }


async def retrieve_context(
    session: AsyncSession,
    *,
    query_embedding: list[float],
    top_k: int,
    min_similarity: float,
    year_from: int | None = None,
    year_to: int | None = None,
    court_level: str | None = None,
    doc_type: str | None = None,
) -> list[SearchResult]:
    """Найти top_k релевантных норм в Qdrant с опциональной фильтрацией."""
    return await vector_store.similarity_search(
        session,
        query_embedding=query_embedding,
        top_k=top_k,
        min_similarity=min_similarity,
        year_from=year_from,
        year_to=year_to,
        court_level=court_level,
        doc_type=doc_type,
    )


async def analyze_document(
    session: AsyncSession,
    *,
    file_bytes: bytes,
    file_name: str,
    llm_client: BaseLLMClient,
    embedder: Embedder | None = None,
    top_k: int | None = None,
    min_similarity: float | None = None,
) -> tuple[AnalysisResult, str]:
    """Поток B: распарсить документ, найти контекст, вызвать LLM на анализ.

    Возвращает кортеж (результат_анализа, полный_текст_документа).
    Полный текст нужен фронту для показа с подсветкой.
    """
    from app.config import get_settings

    settings = get_settings()
    embedder = embedder or Embedder()
    top_k = top_k if top_k is not None else settings.rag_top_k
    min_similarity = (
        min_similarity if min_similarity is not None else settings.rag_min_similarity
    )

    logger.info("Анализ документа «{}»", file_name)
    parsed = parse_document(file_bytes, file_name=file_name)
    document_text = parsed.full_text
    logger.info(
        "Документ распарсен: формат {}, {} символов", parsed.file_type, parsed.total_chars
    )

    # Векторизуем документ целиком (как запрос) для поиска релевантных норм
    query_embedding = embedder.embed_text(document_text[:8000])
    context = await retrieve_context(
        session,
        query_embedding=query_embedding,
        top_k=top_k,
        min_similarity=min_similarity,
    )
    logger.info(
        "Найдено {} релевантных норм для документа «{}»", len(context), file_name
    )

    result = await llm_client.analyze(
        document_text=document_text,
        file_name=file_name,
        context=context,
    )
    return result, document_text
