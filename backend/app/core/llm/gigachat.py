"""GigaChat (Сбер) — реализация LLM-клиента.

Использует официальную библиотеку gigachat, которая сама:
  - обменивает credentials (base64-ключ) на access_token
  - обновляет токен каждые 30 минут
  - подключает сертификаты Минцифры (verify_ssl_certs)

Ваши credentials из личного кабинета GigaChat хранятся в .env (GIGACHAT_API_KEY).
"""
import json
import re

from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import get_settings
from app.core.llm.base import BaseLLMClient
from app.core.prompt_logger import log_prompt
from app.db.vector_store import SearchResult
from app.schemas.analysis import AnalysisResult

settings = get_settings()

SYSTEM_PROMPT = """Ты — опытный юридический ассистент для юристов России.
Твоя задача — проанализировать документ, опираясь ТОЛЬКО на предоставленные нормы
права и судебную практику (контекст ниже), и дать структурированный ответ.

Правила:
1. Опирайся исключительно на предоставленный контекст. Если нормы недостаточно —
   честно укажи это.
2. На каждую рекомендацию и риск ссылайся на конкретную статью/пункт.
3. ВАЖНО про подсветки: выделяй ТОЛЬКО риски и рекомендации (проблемные места).
   НЕ выделяй «положительные» моменты, правильные формулировки или нейтральный
   текст. Каждая подсветка должна быть проблемной — требующей внимания юриста.
4. Для каждой рекомендации укажи точную цитату из документа (quote) — фрагмент,
   к которому она относится.
5. Отвечай СТРОГО в формате JSON по указанной схеме. Без markdown-обёрток, без
   пояснений до/после JSON."""


class GigaChatLLMClient(BaseLLMClient):
    provider_name = "gigachat"

    def __init__(self) -> None:
        # Ленивый импорт — тяжёлая зависимость
        from gigachat import GigaChat

        # verify_ssl_certs=False — отключаем проверку русского сертификата
        # Минцифры (в продакшене лучше подключить russian_trusted_root_ca.cer).
        # Библиотека сама кэширует и обновляет access_token каждые 30 минут.
        self._client = GigaChat(
            credentials=settings.gigachat_api_key,
            scope=settings.gigachat_scope,
            model=settings.gigachat_model,
            verify_ssl_certs=False,
            timeout=120,
        )
        logger.info(
            "GigaChat клиент создан (model={})", settings.gigachat_model
        )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=15))
    async def analyze(
        self,
        *,
        document_text: str,
        file_name: str,
        context: list[SearchResult],
    ) -> AnalysisResult:
        context_block = self._format_context(context)
        user_prompt = self._build_user_prompt(file_name, document_text, context_block)

        logger.info(
            "[GigaChat] Запрос (документ {} символов, контекст {} фрагментов)",
            len(document_text),
            len(context),
        )

        # Библиотека gigachat синхронная — вызываем через asyncio.to_thread,
        # чтобы не блокировать event loop FastAPI.
        import asyncio

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]
        try:
            response = await asyncio.to_thread(
                self._client.chat, {"messages": messages, "temperature": 0.2}
            )
            raw = response.choices[0].message.content or "{}"
            logger.debug("[GigaChat] Сырой ответ ({} символов)", len(raw))

            # --- Логирование промта и ответа в файл ---
            usage = getattr(response, "usage", None)
            _log_request(
                provider=self.provider_name,
                system_prompt=SYSTEM_PROMPT,
                user_prompt=user_prompt,
                context=context,
                response=raw,
                file_name=file_name,
                extra={
                    "model": settings.gigachat_model,
                    "temperature": 0.2,
                    "prompt_tokens": getattr(usage, "prompt_tokens", "?") if usage else "?",
                    "completion_tokens": getattr(usage, "completion_tokens", "?") if usage else "?",
                    "total_tokens": getattr(usage, "total_tokens", "?") if usage else "?",
                },
            )
        except Exception as exc:
            # Логируем упавший запрос тоже — для отладки
            _log_request(
                provider=self.provider_name,
                system_prompt=SYSTEM_PROMPT,
                user_prompt=user_prompt,
                context=context,
                response=None,
                error=str(exc),
                file_name=file_name,
            )
            raise

        data = _extract_json(raw)
        data["llm_provider"] = self.provider_name

        # references дублируем из найденного контекста с полными цитатами
        data.setdefault("references", [
            {
                "title": r.document_title,
                "article_ref": r.article_ref,
                "quote": r.text[:400],
                "doc_type": r.doc_type,
                "similarity": round(r.similarity, 3),
            }
            for r in context[:5]
        ])

        return AnalysisResult.model_validate(data)

    @staticmethod
    def _format_context(context: list[SearchResult]) -> str:
        if not context:
            return "(контекст пуст — база знаний не содержит релевантных норм)"
        blocks = []
        for i, r in enumerate(context, start=1):
            ref = r.document_title
            if r.article_ref:
                ref += f", {r.article_ref}"
            blocks.append(
                f"[{i}] Источник: {ref} (тип: {r.doc_type})\n{r.text}"
            )
        return "\n\n".join(blocks)

    @staticmethod
    def _build_user_prompt(file_name: str, document_text: str, context: str) -> str:
        return f"""Проанализируй следующий документ юриста и верни ответ в JSON.

=== КОНТЕКСТ: НОРМЫ ПРАВА И СУДЕБНАЯ ПРАКТИКА ===
{context}
=== КОНЕЦ КОНТЕКСТА ===

=== АНАЛИЗИРУЕМЫЙ ДОКУМЕНТ ({file_name}) ===
{document_text[:12000]}
=== КОНЕЦ ДОКУМЕНТА ===

Верни JSON строго следующей структуры (без markdown, без текста вне JSON):
{{
  "summary": "краткое резюме документа и анализа (2-4 предложения)",
  "recommendations": [
    {{"text": "конкретная рекомендация", "category": "compliance|risk|missing_clause|wording|general", "quote": "точная цитата из документа, к которой относится рекомендация"}}
  ],
  "risks": [
    {{"text": "описание риска", "severity": "high|medium|low", "quote": "точная цитата из документа, где найден риск"}}
  ],
  "highlights": [
    {{"quote": "точная цитата проблемного фрагмента из документа", "severity": "risk|recommendation", "comment": "пояснение"}}
  ]
}}"""


def _log_request(
    *,
    provider: str,
    system_prompt: str,
    user_prompt: str,
    context: list[SearchResult],
    response: str | None,
    file_name: str | None = None,
    error: str | None = None,
    extra: dict | None = None,
) -> None:
    """Сериализовать контекст и записать промт+ответ в logs/prompts.log."""
    from app.config import get_settings

    s = get_settings()
    if not s.prompt_log_enabled:
        return

    context_chunks = [
        {
            "title": r.document_title,
            "article_ref": r.article_ref,
            "similarity": r.similarity,
        }
        for r in context
    ]
    log_prompt(
        provider=provider,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        context_chunks=context_chunks,
        response=response,
        error=error,
        file_name=file_name,
        extra=extra,
    )


def _extract_json(raw: str) -> dict:
    """Достать JSON из ответа модели.

    GigaChat иногда оборачивает ответ в ```json ... ``` или добавляет текст
    вокруг. Пытаемся извлечь JSON максимально устойчиво.
    """
    raw = raw.strip()

    # 1. Прямой парсинг — если ответ чистый JSON
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # 2. Извлечение из markdown-блока ```json ... ```
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # 3. Поиск первого {...} блока в тексте
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    logger.warning("Не удалось распарсить JSON из ответа GigaChat. Возвращаем пустую структуру.")
    return {
        "summary": "Ошибка парсинга ответа модели. Сырой ответ сохранён в логах.",
        "recommendations": [],
        "risks": [],
        "highlights": [],
    }
