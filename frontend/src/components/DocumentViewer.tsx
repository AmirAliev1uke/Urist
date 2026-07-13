import { forwardRef } from 'react'
import type { Risk, Recommendation } from '../types'
import { HighlightLayer } from './HighlightLayer'

interface Props {
  text: string
  risks: Risk[]
  recommendations: Recommendation[]
  fileName: string
}

/**
 * Просмотрщик текста документа с подсветкой.
 * forwardRef позволяет родителю прокручивать контейнер к нужной подсветке.
 */
export const DocumentViewer = forwardRef<HTMLDivElement, Props>(
  function DocumentViewer({ text, risks, recommendations, fileName }, ref) {
    return (
      <div className="panel" ref={ref}>
        <h2>📄 Документ: {fileName}</h2>
        {text ? (
          <HighlightLayer text={text} risks={risks} recommendations={recommendations} />
        ) : (
          <div className="empty">
            Текст документа появится здесь после анализа.
          </div>
        )}
      </div>
    )
  },
)
