"""Фабрика LLM-клиентов: выбирает реализацию по LLM_PROVIDER из конфига.

stub      — мок без внешних вызовов (по умолчанию)
gigachat  — Сбер GigaChat (заготовка)
openai    — OpenAI GPT (заготовка)
yandex    — YandexGPT (заготовка)

Чтобы добавить реальный провайдер: реализуйте BaseLLMClient и подключите здесь.
"""
from loguru import logger

from app.config import get_settings
from app.core.llm.base import BaseLLMClient
from app.core.llm.stub import StubLLMClient

settings = get_settings()


def get_llm_client() -> BaseLLMClient:
    """Возвращает LLM-клиент согласно настройкам."""
    provider = settings.llm_provider.lower().strip()

    if provider == "stub":
        logger.info("LLM-провайдер: stub (заглушка, без внешнего API)")
        return StubLLMClient()

    # --- Реальные провайдеры (раскомментировать после добавления API-ключа) ---
    if provider == "openai":
        if not settings.openai_api_key:
            logger.warning(
                "LLM_PROVIDER=openai, но OPENAI_API_KEY пуст. Падаю обратно на stub."
            )
            return StubLLMClient()
        from app.core.llm.openai_client import OpenAILLMClient  # noqa: WPS433

        logger.info("LLM-провайдер: OpenAI ({})", settings.openai_model)
        return OpenAILLMClient()

    if provider == "gigachat":
        if not settings.gigachat_api_key:
            logger.warning(
                "LLM_PROVIDER=gigachat, но GIGACHAT_API_KEY пуст. "
                "Падаю обратно на stub."
            )
            return StubLLMClient()
        from app.core.llm.gigachat import GigaChatLLMClient  # noqa: WPS433

        logger.info("LLM-провайдер: GigaChat")
        return GigaChatLLMClient()

    if provider == "gemini":
        if not settings.gemini_api_key:
            logger.warning(
                "LLM_PROVIDER=gemini, но GEMINI_API_KEY пуст. Падаю обратно на stub."
            )
            return StubLLMClient()
        from app.core.llm.gemini import GeminiLLMClient  # noqa: WPS433

        logger.info("LLM-провайдер: Gemini ({})", settings.gemini_model)
        return GeminiLLMClient()

    logger.warning(
        "Неизвестный LLM_PROVIDER='{}'. Доступно: stub | gigachat | openai | yandex. "
        "Использую stub.", provider
    )
    return StubLLMClient()
