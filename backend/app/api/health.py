"""Health-check эндпоинты."""
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.database import get_session
from app.db.vector_store import count_chunks

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    """Базовая liveliness-проверка."""
    return {"status": "ok", "service": "legal-ai-assistant"}


@router.get("/health/db")
async def health_db(session: AsyncSession = Depends(get_session)) -> dict:
    """Проверка связи с PostgreSQL и Qdrant."""
    # PostgreSQL
    try:
        pg_ok = (await session.execute(text("SELECT 1"))).scalar()
        docs_count = (
            await session.execute(text("SELECT count(*) FROM knowledge_documents"))
        ).scalar()
        analyses_count = (
            await session.execute(text("SELECT count(*) FROM analyses"))
        ).scalar()
        pg_status = {"status": "ok", "select_1": pg_ok, "documents": docs_count, "analyses": analyses_count}
    except Exception as exc:  # noqa: BLE001
        pg_status = {"status": "error", "detail": str(exc)}

    # Qdrant
    try:
        chunks = await count_chunks()
        qdrant_status = {"status": "ok", "total_chunks": chunks}
    except Exception as exc:  # noqa: BLE001
        qdrant_status = {"status": "error", "detail": str(exc)}

    return {"postgres": pg_status, "qdrant": qdrant_status}


@router.get("/config")
async def config_info() -> dict:
    """Текущая конфигурация (без секретов) — удобно для отладки на старте."""
    s = get_settings()
    return {
        "llm_provider": s.llm_provider,
        "embedding_model": s.embedding_model,
        "embedding_dim": s.embedding_dim,
        "rag_top_k": s.rag_top_k,
        "rag_min_similarity": s.rag_min_similarity,
        "qdrant_url": s.qdrant_url,
        "qdrant_collection": s.qdrant_collection,
    }
