import { useState } from 'react'
import type { AnalysisResult, LegalReference, Risk } from '../types'
import { ReferenceModal } from './ReferenceModal'

interface Props {
  result: AnalysisResult
  /** Вызывается при клике на риск — перенос к фрагменту в документе */
  onRiskClick?: (index: number) => void
  /** Вызывается при клике на рекомендацию — перенос к фрагменту в документе */
  onRecommendationClick?: (index: number) => void
}

const categoryLabels: Record<string, string> = {
  compliance: 'Соответствие закону',
  risk: 'Риск',
  missing_clause: 'Отсутствует условие',
  wording: 'Формулировка',
  general: 'Общее',
}

export function AnalysisReport({ result, onRiskClick, onRecommendationClick }: Props) {
  const [openRef, setOpenRef] = useState<LegalReference | null>(null)

  return (
    <div className="panel">
      <h2>
        🤖 Отчёт ИИ
        <span className="provider-tag">{result.llm_provider}</span>
      </h2>

      {/* Резюме */}
      <div className="report-section">
        <h3>Краткое резюме</h3>
        <div className="summary-box">{result.summary}</div>
      </div>

      {/* Рекомендации */}
      {result.recommendations.length > 0 && (
        <div className="report-section">
          <h3>Рекомендации ({result.recommendations.length})</h3>
          {result.recommendations.map((rec, i) => {
            const isClickable = rec.quote && onRecommendationClick
            return (
              <div
                key={i}
                className={`card card-${rec.category}${isClickable ? ' card-clickable' : ''}`}
                onClick={() => isClickable && onRecommendationClick!(i)}
                role={isClickable ? 'button' : undefined}
                tabIndex={isClickable ? 0 : undefined}
              >
                <div className="card-title">{rec.text}</div>
                <div className="card-meta">
                  {categoryLabels[rec.category] ?? rec.category}
                  {isClickable && <span className="card-hint"> → к тексту</span>}
                </div>
                {rec.references.length > 0 && (
                  <div className="card-meta" style={{ marginTop: 6 }}>
                    Основание: {rec.references.map((r) => r.article_ref || r.title).join(', ')}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}

      {/* Риски */}
      {result.risks.length > 0 && (
        <div className="report-section">
          <h3>Выявленные риски ({result.risks.length})</h3>
          {result.risks.map((risk: Risk, i) => {
            const isClickable = risk.quote && onRiskClick
            return (
              <div
                key={i}
                className={`card card-risk-${risk.severity}${isClickable ? ' card-clickable' : ''}`}
                onClick={() => isClickable && onRiskClick!(i)}
                role={isClickable ? 'button' : undefined}
                tabIndex={isClickable ? 0 : undefined}
              >
                <div className="card-title">
                  {risk.text}
                  <span className={`badge badge-risk-${risk.severity}`} style={{ marginLeft: 8 }}>
                    {risk.severity}
                  </span>
                </div>
                {risk.quote && (
                  <div className="card-meta">
                    «{risk.quote}»
                    {isClickable && <span className="card-hint"> → к тексту</span>}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}

      {/* Релевантные нормы — кликабельны, открывают модальное окно */}
      {result.references.length > 0 && (
        <div className="report-section">
          <h3>Нормы права и практика ({result.references.length})</h3>
          {result.references.map((ref, i) => (
            <div
              key={i}
              className="ref-item card-clickable"
              onClick={() => setOpenRef(ref)}
              role="button"
              tabIndex={0}
            >
              <div className="ref-title">
                {ref.title}
                {ref.article_ref ? ` · ${ref.article_ref}` : ''}
                <span className="card-hint"> → открыть полностью</span>
                <span style={{ float: 'right', color: 'var(--text-dim)', fontSize: 11 }}>
                  {Math.round(ref.similarity * 100)}%
                </span>
              </div>
              <div className="ref-quote">{ref.quote.slice(0, 120)}…</div>
              <div className="similarity-bar">
                <div
                  className="similarity-fill"
                  style={{ width: `${Math.round(ref.similarity * 100)}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      )}

      <ReferenceModal reference={openRef} onClose={() => setOpenRef(null)} />
    </div>
  )
}
