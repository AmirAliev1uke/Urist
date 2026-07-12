"""Извлечение текста из PDF с помощью PyMuPDF.

Для сканированных PDF (без текстового слоя) здесь можно позже добавить OCR,
но для большинства кодексов/законов текстового слоя достаточно.
"""
from dataclasses import dataclass

import fitz  # PyMuPDF


@dataclass
class ParsedPage:
    page_number: int  # 1-based
    text: str


@dataclass
class ParsedDocument:
    """Результат извлечения текста из PDF."""

    file_name: str
    pages: list[ParsedPage]
    total_chars: int

    @property
    def full_text(self) -> str:
        return "\n\n".join(p.text for p in self.pages)


def parse_pdf(file_bytes: bytes, file_name: str = "document.pdf") -> ParsedDocument:
    """Распарсить PDF и вернуть текст постранично.

    Бросает ValueError, если PDF пустой или повреждён.
    """
    pages: list[ParsedPage] = []
    try:
        with fitz.open(stream=file_bytes, filetype="pdf") as doc:
            for i, page in enumerate(doc, start=1):
                text = page.get_text("text").strip()
                pages.append(ParsedPage(page_number=i, text=text))
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"Не удалось распарсить PDF: {exc}") from exc

    total_chars = sum(len(p.text) for p in pages)
    if total_chars == 0:
        raise ValueError(
            "PDF не содержит текстового слоя. "
            "Возможно, это скан — потребуется OCR (ещё не реализовано)."
        )

    return ParsedDocument(file_name=file_name, pages=pages, total_chars=total_chars)
