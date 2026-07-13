import { useRef, useState } from 'react'
import type { AnalysisResponse } from './types'
import { DocumentUpload } from './components/DocumentUpload'
import { AnalysisReport } from './components/AnalysisReport'
import { DocumentViewer } from './components/DocumentViewer'
import { KnowledgeBase } from './components/KnowledgeBase'

type Tab = 'analyze' | 'knowledge'

export default function App() {
  const [tab, setTab] = useState<Tab>('analyze')
  const [analysis, setAnalysis] = useState<AnalysisResponse | null>(null)
  const viewerRef = useRef<HTMLDivElement>(null)

  /** Прокрутить документ к элементу подсветки по id вида "risk:0" / "recommendation:1" */
  const scrollToHighlight = (id: string) => {
    const panel = viewerRef.current
    if (!panel) return
    const el = panel.querySelector(`#${CSS.escape(id)}`) as HTMLElement | null
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'center' })
      // Краткая пульсация для привлечения внимания
      el.classList.add('hl-pulse')
      setTimeout(() => el.classList.remove('hl-pulse'), 1500)
    }
  }

  const handleRiskClick = (index: number) => {
    scrollToHighlight(`risk:${index}`)
  }

  const handleRecommendationClick = (index: number) => {
    scrollToHighlight(`recommendation:${index}`)
  }

  return (
    <div className="app">
      <header className="header">
        <div>
          <h1>
            ⚖️ Legal AI Assistant
            <span className="subtitle">— анализ документов на основе норм права РФ</span>
          </h1>
        </div>
        <nav>
          <button
            className={`tab-btn ${tab === 'analyze' ? 'active' : ''}`}
            onClick={() => setTab('analyze')}
          >
            Анализ документа
          </button>
          <button
            className={`tab-btn ${tab === 'knowledge' ? 'active' : ''}`}
            onClick={() => setTab('knowledge')}
          >
            База знаний
          </button>
        </nav>
      </header>

      <main className="main">
        {tab === 'analyze' &&
          (analysis?.result ? (
            <div className="split">
              <DocumentViewer
                ref={viewerRef}
                text={analysis.document_text || ''}
                risks={analysis.result.risks}
                recommendations={analysis.result.recommendations}
                fileName={analysis.file_name}
              />
              <AnalysisReport
                result={analysis.result}
                onRiskClick={handleRiskClick}
                onRecommendationClick={handleRecommendationClick}
              />
            </div>
          ) : (
            <DocumentUpload onAnalyzed={setAnalysis} />
          ))}

        {tab === 'knowledge' && <KnowledgeBase />}
      </main>
    </div>
  )
}
