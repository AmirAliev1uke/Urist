import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useDropzone } from 'react-dropzone'
import {
  deleteKnowledgeDocument,
  listKnowledgeDocuments,
  uploadKnowledgePdf,
} from '../api/client'
import type { DocType } from '../types'

const docTypeLabels: Record<DocType, string> = {
  code: 'Кодекс',
  judicial_practice: 'Судебная практика',
  law: 'Закон',
  other: 'Другое',
}

export function KnowledgeBase() {
  const qc = useQueryClient()
  const { data: documents = [], isLoading } = useQuery({
    queryKey: ['knowledge-docs'],
    queryFn: listKnowledgeDocuments,
  })

  const [title, setTitle] = useState('')
  const [docType, setDocType] = useState<DocType>('code')
  const [sourceUrl, setSourceUrl] = useState('')
  const [selectedFile, setSelectedFile] = useState<File | null>(null)

  const uploadMutation = useMutation({
    mutationFn: () => {
      if (!selectedFile) throw new Error('Выберите PDF-файл')
      return uploadKnowledgePdf(selectedFile, { title, doc_type: docType, source_url: sourceUrl })
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['knowledge-docs'] })
      setTitle('')
      setSourceUrl('')
      setSelectedFile(null)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: number) => deleteKnowledgeDocument(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['knowledge-docs'] }),
  })

  const { getRootProps, getInputProps } = useDropzone({
    onDrop: (files) => setSelectedFile(files[0] ?? null),
    accept: {
      'application/pdf': ['.pdf'],
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
      'application/msword': ['.doc'],
    },
    multiple: false,
  })

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: 20 }}>
      {/* Форма загрузки */}
      <div className="panel">
        <h2>⬆ Загрузить источник права</h2>
        <div {...getRootProps()} className="dropzone" style={{ padding: 24, marginBottom: 16 }}>
          <input {...getInputProps()} />
          {selectedFile ? (
            <div>📎 {selectedFile.name} ({Math.round(selectedFile.size / 1024)} КБ)</div>
          ) : (
            <div className="dz-hint">Нажмите или перетащите PDF/DOCX/DOC (ГК РФ, НК РФ, практика…)</div>
          )}
        </div>

        <div className="form-row">
          <label>Название *</label>
          <input value={title} onChange={(e) => setTitle(e.target.value)}
            placeholder="Гражданский кодекс РФ, Часть 1" />
        </div>
        <div className="form-row">
          <label>Тип источника</label>
          <select value={docType} onChange={(e) => setDocType(e.target.value as DocType)}>
            <option value="code">Кодекс</option>
            <option value="law">Закон</option>
            <option value="judicial_practice">Судебная практика</option>
            <option value="other">Другое</option>
          </select>
        </div>
        <div className="form-row">
          <label>Источник (URL, необязательно)</label>
          <input value={sourceUrl} onChange={(e) => setSourceUrl(e.target.value)}
            placeholder="https://pravo.gov.ru/..." />
        </div>

        <button
          className="btn"
          style={{ width: '100%' }}
          disabled={!title || !selectedFile || uploadMutation.isPending}
          onClick={() => uploadMutation.mutate()}
        >
          {uploadMutation.isPending ? 'Загрузка и индексация…' : 'Загрузить в базу знаний'}
        </button>

        {uploadMutation.isError && (
          <div style={{ marginTop: 12, color: 'var(--risk)', fontSize: 13 }}>
            ⚠ {uploadMutation.error instanceof Error ? uploadMutation.error.message : 'Ошибка'}
          </div>
        )}
        {uploadMutation.isSuccess && (
          <div style={{ marginTop: 12, color: 'var(--ok)', fontSize: 13 }}>
            ✓ {uploadMutation.data.message}
          </div>
        )}
      </div>

      {/* Список документов */}
      <div className="panel">
        <h2>📚 База знаний ({documents.length})</h2>
        {isLoading ? (
          <div className="loading"><div className="spinner" /> Загрузка…</div>
        ) : documents.length === 0 ? (
          <div className="empty">
            База знаний пуста. Загрузите законы и судебную практику,
            чтобы ассистент мог опираться на них при анализе.
          </div>
        ) : (
          <table className="kb-table">
            <thead>
              <tr>
                <th>Название</th>
                <th>Тип</th>
                <th>Чанков</th>
                <th>Дата</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {documents.map((d) => (
                <tr key={d.id}>
                  <td>{d.title}</td>
                  <td>{docTypeLabels[d.doc_type] ?? d.doc_type}</td>
                  <td>{d.total_chunks}</td>
                  <td style={{ color: 'var(--text-dim)', fontSize: 12 }}>
                    {new Date(d.created_at).toLocaleDateString('ru-RU')}
                  </td>
                  <td>
                    <button
                      className="btn btn-danger"
                      style={{ padding: '4px 10px', fontSize: 12 }}
                      onClick={() => deleteMutation.mutate(d.id)}
                    >
                      Удалить
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
