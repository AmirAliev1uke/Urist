import type { HighlightSpan } from '../types'
import { HighlightLayer } from './HighlightLayer'

interface Props {
  text: string
  highlights: HighlightSpan[]
  fileName: string
}

export function DocumentViewer({ text, highlights, fileName }: Props) {
  return (
    <div className="panel">
      <h2>📄 Документ: {fileName}</h2>
      {text ? (
        <HighlightLayer text={text} highlights={highlights} />
      ) : (
        <div className="empty">
          Текст документа появится здесь после анализа.
          <br />
          (В текущей версии отдаём только ответ ИИ — хранение исходного текста можно включить.)
        </div>
      )}
    </div>
  )
}
