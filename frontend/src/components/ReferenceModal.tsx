import { useEffect } from 'react'
import type { LegalReference } from '../types'

interface Props {
  reference: LegalReference | null
  onClose: () => void
}

const docTypeLabels: Record<string, string> = {
  code: 'Кодекс',
  law: 'Закон',
  judicial_practice: 'Судебная практика',
  other: 'Документ',
}

/**
 * Модальное окно для просмотра полного текста найденной нормы права.
 * Открывается по клику на норму в отчёте, закрывается крестиком или Esc.
 */
export function ReferenceModal({ reference, onClose }: Props) {
  // Закрытие по Esc
  useEffect(() => {
    if (!reference) return
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [reference, onClose])

  if (!reference) return null

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div>
            <div className="modal-title">
              {reference.title}
              {reference.article_ref ? ` · ${reference.article_ref}` : ''}
            </div>
            <div className="modal-meta">
              {docTypeLabels[reference.doc_type] || reference.doc_type}
              {reference.similarity > 0 && (
                <span className="modal-sim">
                  релевантность {Math.round(reference.similarity * 100)}%
                </span>
              )}
            </div>
          </div>
          <button className="modal-close" onClick={onClose} aria-label="Закрыть">
            ✕
          </button>
        </div>
        <div className="modal-body">
          {reference.quote}
        </div>
      </div>
    </div>
  )
}
