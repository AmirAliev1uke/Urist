"""Pydantic-схемы результата анализа документа.

Эта структура — «контракт» между LLM-слоем и фронтендом.
LLM (любой провайдер) должен вернуть объект AnalysisResult.
"""
from pydantic import BaseModel, Field


class HighlightSpan(BaseModel):
    """Подсветка фрагмента в тексте документа юриста."""

    quote: str = Field(..., description="Фрагмент текста документа для подсветки")
    severity: str = Field(
        "info", description="risk | recommendation | reference | info"
    )
    comment: str = Field("", description="Комментарий ИИ к этому фрагменту")


class LegalReference(BaseModel):
    """Найденная в базе знаний норма права или судебная практика."""

    title: str = Field(..., description="Название источника (напр. «ГК РФ»)")
    article_ref: str | None = Field(None, description="Статья/пункт (напр. «ст. 152»)")
    quote: str = Field(..., description="Цитата релевантного фрагмента")
    doc_type: str = Field("other", description="code | judicial_practice | law | other")
    similarity: float = Field(0.0, description="Оценка релевантности 0..1")


class Recommendation(BaseModel):
    """Рекомендация ИИ юристу."""

    text: str = Field(..., description="Текст рекомендации")
    category: str = Field(
        "general",
        description="compliance | risk | missing_clause | wording | general",
    )
    references: list[LegalReference] = Field(default_factory=list)


class Risk(BaseModel):
    """Выявленный риск в документе."""

    text: str = Field(..., description="Описание риска")
    severity: str = Field("medium", description="high | medium | low")
    quote: str | None = Field(None, description="Фрагмент документа, где найден риск")


class AnalysisResult(BaseModel):
    """Полный результат анализа документа."""

    summary: str = Field(..., description="Краткое резюме документа и анализа")
    recommendations: list[Recommendation] = Field(default_factory=list)
    risks: list[Risk] = Field(default_factory=list)
    highlights: list[HighlightSpan] = Field(default_factory=list)
    references: list[LegalReference] = Field(
        default_factory=list,
        description="Все релевантные нормы, использованные для анализа",
    )
    llm_provider: str = Field("stub", description="Какой ИИ сформировал ответ")


class AnalysisResponse(BaseModel):
    """Ответ API анализа документа."""

    id: int
    file_name: str
    status: str
    result: AnalysisResult | None = None
    error: str | None = None
    created_at: str
