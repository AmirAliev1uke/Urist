"""Stub-реализация LLM.

Возвращает правдоподобный мок-ответ БЕЗ вызова внешнего API.
Позволяет разрабатывать и тестировать весь сервис (бэкенд + фронтенд),
не имея API-ключа. Когда ключ появится — переключите LLM_PROVIDER в .env.
"""
from loguru import logger

from app.core.llm.base import BaseLLMClient
from app.db.vector_store import SearchResult
from app.schemas.analysis import (
    AnalysisResult,
    HighlightSpan,
    LegalReference,
    Recommendation,
    Risk,
)


class StubLLMClient(BaseLLMClient):
    provider_name = "stub"

    async def analyze(
        self,
        *,
        document_text: str,
        file_name: str,
        context: list[SearchResult],
    ) -> AnalysisResult:
        logger.info(
            "[STUB] Анализ документа «{}» ({} символов), контекст: {} фрагментов",
            file_name,
            len(document_text),
            len(context),
        )

        # Превращаем найденные нормы в ссылки для отчёта
        references = [
            LegalReference(
                title=r.document_title,
                article_ref=r.article_ref,
                quote=r.text[:300] + ("…" if len(r.text) > 300 else ""),
                doc_type=r.doc_type,
                similarity=round(r.similarity, 3),
            )
            for r in context[:5]
        ]

        recommendations: list[Recommendation] = [
            Recommendation(
                text=(
                    "Подключите реальный LLM-провайдер (GigaChat/OpenAI/Yandex), "
                    "установив LLM_PROVIDER в .env и добавив API-ключ. "
                    "Сейчас работает stub-заглушка."
                ),
                category="general",
                quote=None,
                references=[],
            )
        ]

        risks: list[Risk] = [
            Risk(
                text=(
                    "Текст документа проанализирован в режиме заглушки (stub). "
                    "Реальные риски будут выявлены после подключения ИИ."
                ),
                severity="low",
                quote=None,
            )
        ]

        # В stub-режиме подсветок нет (только реальные риски/рекомендации подсвечиваются)
        highlights: list[HighlightSpan] = []

        return AnalysisResult(
            summary=(
                f"Документ «{file_name}» загружен и проанализирован в режиме "
                f"заглушки. Найдено {len(references)} релевантных норм в базе "
                f"знаний. Для полноценного анализа подключите LLM-провайдера."
            ),
            recommendations=recommendations,
            risks=risks,
            highlights=highlights,
            references=references,
            llm_provider=self.provider_name,
        )
