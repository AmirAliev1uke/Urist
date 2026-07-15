"""Gemini (Google AI Studio) — реализация LLM-клиента.

Использует библиотеку google-genai. Поддерживает SOCKS-прокси (V2Ray) для
обхода геоблокировки Gemini в РФ.

Особенности:
  - Прокси: задаётся через LLM_PROXY в .env (socks5://host.docker.internal:1080)
  - Судебная практика: отдельный блок в промпте + схеме (требует проверки!)
  - user_query: дополнительные указания юриста добавляются в промпт
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
Твоя задача — проанализировать документ, опираясь на предоставленные нормы
права и судебную практику, и дать структурированный ответ.

Правила:
1. Опирайся на предоставленный контекст (нормы права). Если нормы недостаточно —
   честно укажи это.
2. ВАЖНО про подсветки: выделяй ТОЛЬКО риски и рекомендации (проблемные места).
   НЕ выделяй «положительные» или нейтральные фрагменты.
3. Для каждой рекомендации и риска укажи точную цитату из документа (quote).
4. СУДЕБНАЯ ПРАКТИКА — крайне важно:
   - Если ты знаешь реальные судебные дела (Пленумы ВС РФ, обзоры практики,
     известные постановления) — укажи их с максимальной полнотой реквизитов.
   - Если ты НЕ уверен в номере дела, дате или суде — ОБЯЗАТЕЛЬНО установи
     needs_verification=true и укажи в поле subject, что реквизиты требуют
     проверки по официальным источникам (sudact.ru, kad.arbitr.ru).
   - НИКОГДА не выдумывай номера дел, которых не существует. Лучше честно
     указать needs_verification=true, чем дать ложный номер.
5. Отвечай СТРОГО в формате JSON по указанной схеме. Без markdown-обёрток."""


class GeminiLLMClient(BaseLLMClient):
    provider_name = "gemini"

    def __init__(self) -> None:
        from google import genai
        from google.genai.types import HttpOptions

        # Настройка прокси, если задан
        client_kwargs = {"api_key": settings.gemini_api_key}
        if settings.llm_proxy:
            # google-genai использует httpx под капотом, прокси передаётся через HttpOptions
            client_kwargs["http_options"] = HttpOptions(proxy=settings.llm_proxy)
            logger.info("Gemini клиент через прокси: {}", settings.llm_proxy)
        else:
            logger.info("Gemini клиент без прокси (прямой доступ)")

        self._client = genai.Client(**client_kwargs)
        self._model = settings.gemini_model
        logger.info("Gemini клиент создан (model={})", self._model)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=15))
    async def analyze(
        self,
        *,
        document_text: str,
        file_name: str,
        context: list[SearchResult],
        user_query: str = "",
    ) -> AnalysisResult:
        context_block = self._format_context(context)
        user_prompt = self._build_user_prompt(
            file_name, document_text, context_block, user_query
        )

        logger.info(
            "[Gemini] Запрос (документ {} символов, контекст {} фрагментов, "
            "user_query: {} символов)",
            len(document_text),
            len(context),
            len(user_query),
        )

        try:
            from google.genai.types import GenerateContentConfig

            response = await self._client.aio.models.generate_content(
                model=self._model,
                contents=user_prompt,
                config=GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    temperature=0.2,
                    max_output_tokens=8000,
                    response_mime_type="application/json",
                ),
            )
            raw = response.text or "{}"
            logger.debug("[Gemini] Сырой ответ ({} символов)", len(raw))

            # Логирование промта
            usage = getattr(response, "usage_metadata", None)
            _log_gemini_request(
                system_prompt=SYSTEM_PROMPT,
                user_prompt=user_prompt,
                context=context,
                response=raw,
                file_name=file_name,
                extra={
                    "model": self._model,
                    "temperature": 0.2,
                    "prompt_tokens": getattr(usage, "prompt_token_count", "?") if usage else "?",
                    "completion_tokens": getattr(usage, "candidates_token_count", "?") if usage else "?",
                    "total_tokens": getattr(usage, "total_token_count", "?") if usage else "?",
                    "proxy": settings.llm_proxy or "нет",
                    "user_query": user_query[:200] if user_query else "нет",
                },
            )
        except Exception as exc:
            _log_gemini_request(
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
            blocks.append(f"[{i}] Источник: {ref} (тип: {r.doc_type})\n{r.text}")
        return "\n\n".join(blocks)

    @staticmethod
    def _build_user_prompt(
        file_name: str,
        document_text: str,
        context: str,
        user_query: str,
    ) -> str:
        user_query_block = ""
        if user_query.strip():
            user_query_block = (
                f"\n\n=== ДОПОЛНИТЕЛЬНЫЕ УКАЗАНИЯ ЮРИСТА ===\n"
                f"{user_query.strip()}\n"
                f"=== КОНЕЦ УКАЗАНИЙ ==="
            )

        return f"""Проанализируй следующий документ юриста и верни ответ в JSON.

=== КОНТЕКСТ: НОРМЫ ПРАВА И СУДЕБНАЯ ПРАКТИКА (из базы знаний) ===
{context}
=== КОНЕЦ КОНТЕКСТА ===

=== АНАЛИЗИРУЕМЫЙ ДОКУМЕНТ ({file_name}) ===
{document_text[:12000]}
=== КОНЕЦ ДОКУМЕНТА ===
{user_query_block}

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
  ],
  "case_law": [
    {{
      "case_number": "номер дела или пусто",
      "court": "наименование суда",
      "date": "дата решения или пусто",
      "subject": "суть дела и правовая позиция",
      "ruling": "вывод суда по существу",
      "relevance": "почему это дело релевантно анализируемому документу",
      "needs_verification": true
    }}
  ]
}}

ВАЖНО про case_law:
- Если не знаешь конкретных дел — верни пустой массив case_law: [].
- Не выдумывай номера дел. Лучше needs_verification=true, чем ложный номер."""


def _log_gemini_request(
    *,
    system_prompt: str,
    user_prompt: str,
    context: list[SearchResult],
    response: str | None,
    file_name: str | None = None,
    error: str | None = None,
    extra: dict | None = None,
) -> None:
    """Записать промт+ответ Gemini в logs/prompts.log."""
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
        provider="gemini",
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        context_chunks=context_chunks,
        response=response,
        error=error,
        file_name=file_name,
        extra=extra,
    )


def _extract_json(raw: str) -> dict:
    """Достать JSON из ответа модели (Gemini обычно отдаёт чистый JSON)."""
    raw = raw.strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Извлечение из markdown-блока
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Поиск первого {...} блока
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    logger.warning("Не удалось распарсить JSON из ответа Gemini.")
    return {
        "summary": "Ошибка парсинга ответа модели. Сырой ответ сохранён в логах.",
        "recommendations": [],
        "risks": [],
        "highlights": [],
        "case_law": [],
    }
