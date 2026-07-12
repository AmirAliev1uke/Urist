import axios from 'axios'
import type { AnalysisResponse, KnowledgeDocument } from '../types'

const BASE_URL = import.meta.env.VITE_API_URL ?? ''

export const api = axios.create({
  baseURL: BASE_URL,
  timeout: 120_000, // анализ может быть долгим
})

// --- База знаний (Поток A) ---

export async function uploadKnowledgePdf(
  file: File,
  fields: { title: string; doc_type: string; source_url?: string },
): Promise<{ status: string; message: string; chunks: number }> {
  const form = new FormData()
  form.append('file', file)
  form.append('title', fields.title)
  form.append('doc_type', fields.doc_type)
  if (fields.source_url) form.append('source_url', fields.source_url)
  const { data } = await api.post('/api/knowledge/upload', form)
  return data
}

export async function listKnowledgeDocuments(): Promise<KnowledgeDocument[]> {
  const { data } = await api.get('/api/knowledge/documents')
  return data
}

export async function deleteKnowledgeDocument(id: number): Promise<void> {
  await api.delete(`/api/knowledge/documents/${id}`)
}

// --- Анализ документа (Поток B) ---

export async function analyzeDocument(file: File): Promise<AnalysisResponse> {
  const form = new FormData()
  form.append('file', file)
  const { data } = await api.post('/api/analyze', form)
  return data
}
