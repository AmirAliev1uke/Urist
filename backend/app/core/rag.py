"""RAG-оркестрация: связывает парсинг, embeddings, поиск и LLM.

Два основных сценария:
  - ingest_document: наполнение базы знаний (Поток A)
  - analyze_document: анализ документа юриста (Поток B)
"""
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.chunker import chunk_document
from app.core.embeddings import Embedder
from app.core.llm.base import BaseLLMClient
from app.core.pdf_parser import parse_pdf
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
) -> int:
    """Поток A: распарсить PDF, чанковать, векторизовать и сохранить в БД.

    Возвращает количество сохранённых чанков.
    """
    embedder = embedder or Embedder()

    logger.info("Ингестия документа «{}» ({} байт)", title, len(file_bytes))
    parsed = parse_pdf(file_bytes, file_name=file_name or title)
    logger.info("Извлечено {} страниц, {} символов", len(parsed.pages), parsed.total_chars)

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
            "metadata": c.metadata or {},
        }
        for c, emb in zip(chunks, embeddings, strict=True)
    ]

    doc = await vector_store.create_document(
        session, title=title, doc_type=doc_type, source_url=source_url, file_name=file_name
    )
    saved = await vector_store.add_chunks(
        session, document_id=doc.id, chunks=payload
    )
    await session.commit()
    logger.info("Сохранено {} чанков для документа id={}", saved, doc.id)
    return saved


async def retrieve_context(
    session: AsyncSession,
    *,
    query_embedding: list[float],
    top_k: int,
    min_similarity: float,
) -> list[SearchResult]:
    """Найти top_k релевантных норм для данного вектора запроса."""
    return await vector_store.similarity_search(
        session,
        query_embedding=query_embedding,
        top_k=top_k,
        min_similarity=min_similarity,
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
) -> AnalysisResult:
    """Поток B: распарсить документ, найти контекст, вызвать LLM на анализ."""
    from app.config import get_settings

    settings = get_settings()
    embedder = embedder or Embedder()
    top_k = top_k if top_k is not None else settings.rag_top_k
    min_similarity = (
        min_similarity if min_similarity is not None else settings.rag_min_similarity
    )

    logger.info("Анализ документа «{}»", file_name)
    parsed = parse_pdf(file_bytes, file_name=file_name)
    document_text = parsed.full_text

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
    return result
