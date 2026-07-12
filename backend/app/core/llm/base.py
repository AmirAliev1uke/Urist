"""Абстрактный интерфейс LLM-клиента.

Любой провайдер (GigaChat, OpenAI, YandexGPT, локальная модель) реализует
этот интерфейс. Это позволяет менять провайдера через LLM_PROVIDER в .env
без изменения остального кода.
"""
from abc import ABC, abstractmethod

from app.schemas.analysis import AnalysisResult
from app.db.vector_store import SearchResult


class BaseLLMClient(ABC):
    """Контракт для всех LLM-провайдеров."""

    provider_name: str = "base"

    @abstractmethod
    async def analyze(
        self,
        *,
        document_text: str,
        file_name: str,
        context: list[SearchResult],
    ) -> AnalysisResult:
        """Проанализировать документ юриста с опорой на найденный контекст.

        Аргументы:
            document_text: полный текст загруженного документа.
            file_name: имя файла (для контекста промпта).
            context: релевантные нормы права, найденные в pgvector.

        Возвращает структурированный AnalysisResult.
        """
        ...
