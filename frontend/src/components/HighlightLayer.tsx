import { useMemo } from 'react'
import type { HighlightSpan } from '../types'

interface Props {
  text: string
  highlights: HighlightSpan[]
}

/**
 * Рендерит текст документа с подсветкой найденных фрагментов.
 * Подсветка накладывается по точному совпадению цитат (quote).
 * Если цитата не найдена в тексте — она пропускается.
 */
export function HighlightLayer({ text, highlights }: Props) {
  const segments = useMemo(() => buildSegments(text, highlights), [text, highlights])

  return (
    <div className="doc-text">
      {segments.map((seg, i) =>
        seg.hl ? (
          <mark
            key={i}
            className={`hl hl-${seg.hl.severity}`}
            title={seg.hl.comment || undefined}
          >
            {seg.text}
          </mark>
        ) : (
          <span key={i}>{seg.text}</span>
        ),
      )}
    </div>
  )
}

type Segment = { text: string; hl: HighlightSpan | null }

function buildSegments(text: string, highlights: HighlightSpan[]): Segment[] {
  if (!highlights.length || !text) {
    return [{ text, hl: null }]
  }

  // Нормализуем цитаты и ищем позиции в тексте
  const matches: { start: number; end: number; hl: HighlightSpan }[] = []
  for (const hl of highlights) {
    const quote = hl.quote.trim()
    if (quote.length < 5) continue // слишком короткие — пропускаем
    const idx = text.indexOf(quote)
    if (idx >= 0) {
      matches.push({ start: idx, end: idx + quote.length, hl })
    }
  }

  if (matches.length === 0) {
    return [{ text, hl: null }]
  }

  // Сортируем по позиции и убираем пересечения
  matches.sort((a, b) => a.start - b.start)
  const filtered: typeof matches = []
  let lastEnd = 0
  for (const m of matches) {
    if (m.start >= lastEnd) {
      filtered.push(m)
      lastEnd = m.end
    }
  }

  // Собираем сегменты: обычный текст + подсвеченный
  const segments: Segment[] = []
  let cursor = 0
  for (const m of filtered) {
    if (m.start > cursor) {
      segments.push({ text: text.slice(cursor, m.start), hl: null })
    }
    segments.push({ text: text.slice(m.start, m.end), hl: m.hl })
    cursor = m.end
  }
  if (cursor < text.length) {
    segments.push({ text: text.slice(cursor), hl: null })
  }
  return segments
}
