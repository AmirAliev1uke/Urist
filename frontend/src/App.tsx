import { useState } from 'react'
import type { AnalysisResponse } from './types'
import { DocumentUpload } from './components/DocumentUpload'
import { AnalysisReport } from './components/AnalysisReport'
import { DocumentViewer } from './components/DocumentViewer'
import { KnowledgeBase } from './components/KnowledgeBase'

type Tab = 'analyze' | 'knowledge'

export default function App() {
  const [tab, setTab] = useState<Tab>('analyze')
  const [analysis, setAnalysis] = useState<AnalysisResponse | null>(null)

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
        {tab === 'analyze' && (
          analysis?.result ? (
            <div className="split">
              <DocumentViewer
                text={analysis.document_text || ''}
                highlights={analysis.result.highlights}
                fileName={analysis.file_name}
              />
              <AnalysisReport result={analysis.result} />
            </div>
          ) : (
            <DocumentUpload onAnalyzed={setAnalysis} />
          )
        )}

        {tab === 'knowledge' && <KnowledgeBase />}
      </main>
    </div>
  )
}
