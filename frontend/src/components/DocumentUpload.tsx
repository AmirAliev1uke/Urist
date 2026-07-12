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

  const onDrop = useCallback(
    async (files: File[]) => {
      const file = files[0]
      if (!file) return
      setLoading(true)
      setError(null)
      try {
        const result = await analyzeDocument(file)
        onAnalyzed(result)
      } catch (e: unknown) {
        const msg =
          e instanceof Error ? e.message : 'Не удалось проанализировать документ'
        setError(msg)
      } finally {
        setLoading(false)
      }
    },
    [onAnalyzed],
  )

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'application/pdf': ['.pdf'] },
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
          Перетащите PDF-документ для анализа
        </div>
        <div className="dz-hint">
          или нажмите для выбора файла · договоры, исковые заявления, проекты законов
        </div>
      </div>
      {error && (
        <div style={{ marginTop: 16, color: 'var(--risk)', fontSize: 14 }}>
          ⚠ {error}
        </div>
      )}
    </div>
  )
}
