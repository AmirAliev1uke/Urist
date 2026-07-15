import { useCallback, useState } from 'react'
import { useDropzone } from 'react-dropzone'
import type { AnalysisResponse } from '../types'
import { analyzeDocument } from '../api/client'

interface Props {
  onAnalyzed: (result: AnalysisResponse) => void
}

export function DocumentUpload({ onAnalyzed }: Props) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [userQuery, setUserQuery] = useState('')

  const onDrop = useCallback(
    async (files: File[]) => {
      const file = files[0]
      if (!file) return
      setLoading(true)
      setError(null)
      try {
        const result = await analyzeDocument(file, userQuery)
        onAnalyzed(result)
      } catch (e: unknown) {
        const msg =
          e instanceof Error ? e.message : 'Не удалось проанализировать документ'
        setError(msg)
      } finally {
        setLoading(false)
      }
    },
    [onAnalyzed, userQuery],
  )

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
      'application/msword': ['.doc'],
    },
    multiple: false,
    disabled: loading,
  })

  if (loading) {
    return (
      <div className="loading">
        <div className="spinner" />
        <div>
          <div style={{ fontSize: 16, marginBottom: 4 }}>Анализ документа…</div>
          <div style={{ fontSize: 13 }}>
            Извлечение текста, поиск релевантных норм, запрос к ИИ…
          </div>
        </div>
      </div>
    )
  }

  return (
    <div>
      <div {...getRootProps()} className={`dropzone ${isDragActive ? 'active' : ''}`}>
        <input {...getInputProps()} />
        <div className="dz-icon">📄</div>
        <div className="dz-title">
          Перетащите документ для анализа
        </div>
        <div className="dz-hint">
          или нажмите для выбора файла · PDF / DOCX / DOC · договоры, иски, проекты
        </div>
      </div>

      <div style={{ marginTop: 20 }}>
        <label style={{ display: 'block', fontSize: 13, color: 'var(--text-dim)', marginBottom: 6 }}>
          Дополнительные указания для ИИ (необязательно)
        </label>
        <textarea
          className="user-query-field"
          placeholder="Например: обратить внимание на порядок расторжения, проверить штрафные санкции, сравнить с типовыми условиями аренды…"
          value={userQuery}
          onChange={(e) => setUserQuery(e.target.value)}
        />
      </div>

      {error && (
        <div style={{ marginTop: 16, color: 'var(--risk)', fontSize: 14 }}>
          ⚠ {error}
        </div>
      )}
    </div>
  )
}
