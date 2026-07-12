"""Health-check эндпоинты."""
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.database import get_session

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    """Базовая liveliness-проверка."""
    return {"status": "ok", "service": "legal-ai-assistant"}


@router.get("/health/db")
async def health_db(session: AsyncSession = Depends(get_session)) -> dict:
    """Проверка связи с БД и расширением pgvector."""
    try:
        # Проверяем, что pgvector доступен
        version = (
            await session.execute(text("SELECT extversion FROM pg_extension WHERE extname='vector'"))
        ).scalar()
        chunks_count = (
            await session.execute(text("SELECT count(*) FROM document_chunks"))
        ).scalar()
        return {
            "status": "ok",
            "pgvector_version": version,
            "total_chunks": chunks_count,
        }
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "detail": str(exc)}


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
    }
