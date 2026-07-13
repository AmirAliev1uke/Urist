"""Конфигурация приложения через переменные окружения."""
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # PostgreSQL
    database_url: str = Field(
        default="postgresql+asyncpg://legal:legal_password@db:5432/legal_ai"
    )

    # LLM provider: stub | gigachat | openai | yandex
    llm_provider: str = "stub"

    # GigaChat
    gigachat_api_key: str = ""
    gigachat_scope: str = "GIGACHAT_API_PERS"
    gigachat_model: str = "GigaChat-2"  # GigaChat | GigaChat-2 | GigaChat-2-Pro | GigaChat-2-Max

    # OpenAI
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    # YandexGPT
    yandex_api_key: str = ""
    yandex_folder_id: str = ""

    # Embeddings
    embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    embedding_dim: int = 384

    # RAG
    rag_top_k: int = 8
    rag_min_similarity: float = 0.3

    # Server
    cors_origins: str = "http://localhost:5173"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
