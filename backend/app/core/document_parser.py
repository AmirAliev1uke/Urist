"""Универсальный парсер документов для анализа (Поток B).

Поддерживаемые форматы:
  - PDF  (через PyMuPDF) — и для базы знаний, и для анализа
  - DOCX (через python-docx) — только для анализа документов юристов

База знаний (Поток A) остаётся только на PDF, как договорили с пользователем.
"""
import io
from dataclasses import dataclass

from app.core.pdf_parser import parse_pdf


@dataclass
class ParsedDocument:
    """Результат извлечения текста из документа любого формата."""

    file_name: str
    file_type: str  # 'pdf' | 'docx'
    pages: list[str]  # текст постранично/поабзацно
    total_chars: int

    @property
    def full_text(self) -> str:
        return "\n\n".join(p for p in self.pages if p.strip())


def parse_document(file_bytes: bytes, file_name: str = "document") -> ParsedDocument:
    """Определить формат по имени файла и распарсить соответствующим парсером.

    Бросает ValueError для неподдерживаемых форматов или пустых документов.
    """
    name = file_name.lower()

    if name.endswith(".pdf"):
        parsed = parse_pdf(file_bytes, file_name=file_name)
        return ParsedDocument(
            file_name=parsed.file_name,
            file_type="pdf",
            pages=[p.text for p in parsed.pages],
            total_chars=parsed.total_chars,
        )

    if name.endswith(".docx"):
        return _parse_docx(file_bytes, file_name)

    if name.endswith(".doc"):
        raise ValueError(
            "Старый формат .doc (Word 97-2003) не поддерживается. "
            "Сохраните файл как .docx и загрузите снова."
        )

    raise ValueError(
        f"Неподдерживаемый формат файла «{file_name}». "
        "Доступные форматы для анализа: PDF, DOCX."
    )


def _parse_docx(file_bytes: bytes, file_name: str) -> ParsedDocument:
    """Извлечь текст из DOCX через python-docx."""
    try:
        from docx import Document  # noqa: WPS433 — ленивый импорт
    except ImportError as exc:
        raise RuntimeError("Библиотека python-docx не установлена.") from exc

    try:
        doc = Document(io.BytesIO(file_bytes))
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"Не удалось прочитать DOCX: {exc}") from exc

    # Текст из абзацев + из таблиц (договоры часто табличные)
    paragraphs: list[str] = [p.text.strip() for p in doc.paragraphs if p.text.strip()]

    for table in doc.tables:
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if cells:
                paragraphs.append(" | ".join(cells))

    if not paragraphs:
        raise ValueError(
            "DOCX не содержит извлекаемого текста. "
            "Возможно, документ состоит только из изображений."
        )

    return ParsedDocument(
        file_name=file_name,
        file_type="docx",
        pages=paragraphs,
        total_chars=sum(len(p) for p in paragraphs),
    )
