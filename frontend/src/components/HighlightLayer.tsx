import { useMemo } from 'react'
import type { Risk, Recommendation } from '../types'

interface Props {
  text: string
  risks: Risk[]
  recommendations: Recommendation[]
}

/**
 * Рендерит текст документа с подсветкой рисков и рекомендаций.
 *
 * Подсветка накладывается по точному совпадению цитат (quote). Цвет подсветки
 * согласован с цветом карточки в отчёте справа:
 *   - risk high    → красный
 *   - risk medium  → жёлтый
 *   - risk low     → зелёный
 *   - recommendation → жёлтый (warning), цвет зависит от категории
 *
 * Цитаты снабжаются id вида {type}:{index}, чтобы из отчёта можно было
 * прокрутить документ к нужному фрагменту.
 */
export function HighlightLayer({ text, risks, recommendations }: Props) {
  const segments = useMemo(
    () => buildSegments(text, risks, recommendations),
    [text, risks, recommendations],
  )

  return (
    <div className="doc-text">
      {segments.map((seg, i) =>
        seg.hl ? (
          <mark
            key={i}
            id={seg.hl.id}
            className={`hl hl-${seg.hl.className}`}
            title={seg.hl.title}
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

type Segment = {
  text: string
  hl: {
    id: string
    className: string
    title: string
  } | null
}

// Соответствие категорий рекомендаций цветам (как в карточках отчёта)
const RECOMMENDATION_COLOR: Record<string, string> = {
  risk: 'risk-high',
  missing_clause: 'risk-medium',
  compliance: 'risk-low',
  wording: 'info',
  general: 'info',
}

// Соответствие severity риска цветам
const RISK_COLOR: Record<string, string> = {
  high: 'risk-high',
  medium: 'risk-medium',
  low: 'risk-low',
}

const COLOR_LABEL: Record<string, string> = {
  'risk-high': 'Высокий риск',
  'risk-medium': 'Средний риск / рекомендация',
  'risk-low': 'Низкий риск / соответствие',
  info: 'Рекомендация',
}

function buildSegments(
  text: string,
  risks: Risk[],
  recommendations: Recommendation[],
): Segment[] {
  // Собираем все цитаты для подсветки с их цветом и id
  const highlights: Array<{
    quote: string
    className: string
    id: string
  }> = []

  risks.forEach((risk, i) => {
    if (risk.quote && risk.quote.trim().length >= 5) {
      highlights.push({
        quote: risk.quote.trim(),
        className: RISK_COLOR[risk.severity] || 'risk-medium',
        id: `risk:${i}`,
      })
    }
  })

  recommendations.forEach((rec, i) => {
    if (rec.quote && rec.quote.trim().length >= 5) {
      highlights.push({
        quote: rec.quote.trim(),
        className: RECOMMENDATION_COLOR[rec.category] || 'info',
        id: `recommendation:${i}`,
      })
    }
  })

  if (!highlights.length || !text) {
    return [{ text, hl: null }]
  }

  // Находим позиции цитат в тексте
  const matches: Array<{
    start: number
    end: number
    className: string
    id: string
  }> = []

  for (const hl of highlights) {
    const idx = text.indexOf(hl.quote)
    if (idx >= 0) {
      matches.push({
        start: idx,
        end: idx + hl.quote.length,
        className: hl.className,
        id: hl.id,
      })
    }
  }

  if (matches.length === 0) {
    return [{ text, hl: null }]
  }

  // Сортируем и убираем пересечения
  matches.sort((a, b) => a.start - b.start)
  const filtered: typeof matches = []
  let lastEnd = 0
  for (const m of matches) {
    if (m.start >= lastEnd) {
      filtered.push(m)
      lastEnd = m.end
    }
  }

  // Собираем сегменты
  const segments: Segment[] = []
  let cursor = 0
  for (const m of filtered) {
    if (m.start > cursor) {
      segments.push({ text: text.slice(cursor, m.start), hl: null })
    }
    segments.push({
      text: text.slice(m.start, m.end),
      hl: {
        id: m.id,
        className: m.className,
        title: COLOR_LABEL[m.className] || '',
      },
    })
    cursor = m.end
  }
  if (cursor < text.length) {
    segments.push({ text: text.slice(cursor), hl: null })
  }
  return segments
}
