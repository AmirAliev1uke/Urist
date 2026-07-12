"""OpenAI GPT-реализация LLM-клиента.

Запрашивает модель в формате JSON, парсит ответ в AnalysisResult.
Активируется, когда в .env указано LLM_PROVIDER=openai и задан OPENAI_API_KEY.

Получить ключ: https://platform.openai.com/api-keys
"""
import json

from loguru import logger
from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import get_settings
from app.core.llm.base import BaseLLMClient
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
3. Выделяй (в highlights) точные цитаты из анализируемого документа.
4. Отвечай СТРОГО в формате JSON по указанной схеме."""


class OpenAILLMClient(BaseLLMClient):
    provider_name = "openai"

    def __init__(self) -> None:
        self._client = AsyncOpenAI(api_key=settings.openai_api_key)
        self._model = settings.openai_model

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def analyze(
        self,
        *,
        document_text: str,
        file_name: str,
        context: list[SearchResult],
    ) -> AnalysisResult:
        context_block = self._format_context(context)
        user_prompt = self._build_user_prompt(file_name, document_text, context_block)

        logger.info("[OpenAI] Запрос к модели {} (документ {} символов)",
                    self._model, len(document_text))

        response = await self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
            max_tokens=3000,
        )

        raw = response.choices[0].message.content or "{}"
        data = json.loads(raw)
        data["llm_provider"] = self.provider_name

        # references дублируем из найденного контекста (с полнотой цитат)
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
            ref = f"{r.document_title}"
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

Верни JSON строго следующей структуры:
{{
  "summary": "краткое резюме (2-4 предложения)",
  "recommendations": [
    {{"text": "...", "category": "compliance|risk|missing_clause|wording|general"}}
  ],
  "risks": [
    {{"text": "...", "severity": "high|medium|low", "quote": "цитата из документа"}}
  ],
  "highlights": [
    {{"quote": "точная цитата из документа", "severity": "risk|recommendation|reference|info", "comment": "..."}}
  ]
}}"""
