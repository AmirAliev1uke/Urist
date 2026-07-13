"""Точка входа FastAPI-приложения Legal AI Assistant."""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from loguru import logger

from app.api import analysis, health, knowledge
from app.config import get_settings
from app.db.database import engine

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Жизненный цикл: проверка связи с БД при старте."""
    logger.info("Запуск Legal AI Assistant (LLM_PROVIDER={})", settings.llm_provider)
    async with engine.connect() as conn:
        from sqlalchemy import text

        ok = (await conn.execute(text("SELECT 1"))).scalar()
        logger.info("Соединение с БД установлено: SELECT 1 = {}", ok)
    yield
    logger.info("Остановка приложения...")
    await engine.dispose()


app = FastAPI(
    title="Legal AI Assistant",
    description=(
        "AI-ассистент для юристов: анализ документов на основе норм права РФ "
        "(ГК РФ, НК РФ, судебная практика) с векторным поиском (pgvector)."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Роутеры
app.include_router(health.router)
app.include_router(knowledge.router)
app.include_router(analysis.router)

# Раздача статики надстройки Word (taskpane.html и ресурсы)
_addin_dir = os.path.join(os.path.dirname(__file__), "..", "word-addin")
if not os.path.isdir(_addin_dir):
    _addin_dir = "/app/word-addin"
if os.path.isdir(_addin_dir):
    app.mount("/addin", StaticFiles(directory=_addin_dir, html=True), name="addin")
    logger.info("Надстройка Word доступна на /addin/taskpane.html")


@app.get("/")
async def root() -> dict:
    return {
        "service": "Legal AI Assistant",
        "docs": "/docs",
        "frontend": "http://localhost:5173",
    }
