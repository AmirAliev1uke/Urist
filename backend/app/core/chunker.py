"""Чанкование текста юридического документа для векторной БД.

Стратегия:
  1. Попытка разбить по статьям (паттерны вида «Статья 123.» или «Статья 12.3.»).
  2. Если статья слишком большая (> max_chunk_chars) — разрезать по абзацам с
     перекрытием, чтобы не терять контекст.
  3. Если статей не найдено (судебная практика, договоры) — общий чанковщик
     по абзацам с перекрытием.
Каждый чанк помечается ссылкой (article_ref), которую потом показывает LLM.
"""
import re
from dataclasses import dataclass

# Паттерн начала статьи в российских НПА:
#   «Статья 152.» «Статья 12.3.» «Статья 15. ГК РФ»
# Учитываем необязательный перенос строки и заголовок.
ARTICLE_RE = re.compile(
    r"(?=(?:\n\s*|^)\s*Статья\s+(\d+(?:\.\d+)*)\.?\s)",
    re.MULTILINE,
)

DEFAULT_MAX_CHARS = 1500
DEFAULT_OVERLAP_CHARS = 200


@dataclass
class Chunk:
    text: str
    article_ref: str | None = None
    metadata: dict | None = None


def chunk_document(
    text: str,
    *,
    max_chunk_chars: int = DEFAULT_MAX_CHARS,
    overlap_chars: int = DEFAULT_OVERLAP_CHARS,
) -> list[Chunk]:
    """Разбить текст документа на чанки для индексации в pgvector."""
    text = _normalize_whitespace(text)
    if not text.strip():
        return []

    # 1. Пытаемся разбить по статьям.
    article_spans = _split_by_articles(text)

    chunks: list[Chunk] = []
    if article_spans:
        for ref, body in article_spans:
            if len(body) <= max_chunk_chars:
                if body.strip():
                    chunks.append(Chunk(text=body.strip(), article_ref=ref))
            else:
                # Статья слишком большая — дробим по абзацам с перекрытием,
                # сохраняя ссылку на статью в каждом под-чанке.
                for piece in _sliding_window(body, max_chunk_chars, overlap_chars):
                    chunks.append(Chunk(text=piece, article_ref=ref))
    else:
        # 2. Нет статей — общий чанковщик по абзацам.
        for piece in _sliding_window(text, max_chunk_chars, overlap_chars):
            chunks.append(Chunk(text=piece, article_ref=None))

    return [c for c in chunks if c.text.strip()]


def _normalize_whitespace(text: str) -> str:
    """Схлопываем множественные пробелы и переносы, оставляя абзацы."""
    # Убираем «висячие» пробелы в начале строк
    text = re.sub(r"[ \t]+\n", "\n", text)
    # Схлопываем 3+ переноса в два (абзац)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _split_by_articles(text: str) -> list[tuple[str, str]]:
    """Вернуть список (номер_статьи, текст_статьи).

    Если статей меньше 2 — считаем, что разбиение не сработало (возвращаем []).
    """
    matches = list(ARTICLE_RE.finditer(text))
    if len(matches) < 2:
        return []

    spans: list[tuple[str, str]] = []
    for i, m in enumerate(matches):
        ref = f"ст. {m.group(1)}"
        start = m.end()  # после «Статья N. »
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[m.start() : end].strip()
        spans.append((ref, body))
    return spans


def _sliding_window(
    text: str, max_chars: int, overlap: int
) -> list[str]:
    """Разрезать текст на части по границам абзацев с перекрытием."""
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    pieces: list[str] = []
    current: list[str] = []
    current_len = 0

    for para in paragraphs:
        # Если один абзац длиннее лимита — режем его по предложениям.
        if len(para) > max_chars:
            if current:
                pieces.append("\n\n".join(current))
                current, current_len = [], 0
            pieces.extend(_split_long_paragraph(para, max_chars, overlap))
            continue

        if current_len + len(para) + 2 > max_chars and current:
            pieces.append("\n\n".join(current))
            # Перекрытие: оставляем последний абзац для контекста
            if overlap > 0 and current:
                tail = current[-1]
                current = [tail] if len(tail) <= overlap else [tail[-overlap:]]
                current_len = len(current[0])
            else:
                current, current_len = [], 0

        current.append(para)
        current_len += len(para) + 2

    if current:
        pieces.append("\n\n".join(current))

    return pieces


def _split_long_paragraph(text: str, max_chars: int, overlap: int) -> list[str]:
    """Режем слишком длинный абзац по предложениям."""
    sentences = re.split(r"(?<=[.!?])\s+", text)
    pieces: list[str] = []
    current = ""

    for sent in sentences:
        if len(current) + len(sent) + 1 > max_chars and current:
            pieces.append(current.strip())
            current = sent if overlap <= 0 else text[max(0, len(current) - overlap):]
        else:
            current = f"{current} {sent}".strip() if current else sent

    if current.strip():
        pieces.append(current.strip())
    return pieces
