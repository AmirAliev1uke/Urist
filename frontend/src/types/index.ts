// Зеркало Pydantic-схем бэкенда (app/schemas/analysis.py)

export type Severity = 'risk' | 'recommendation' | 'reference' | 'info'
export type DocType = 'code' | 'judicial_practice' | 'law' | 'other'
export type RiskSeverity = 'high' | 'medium' | 'low'
export type RecommendationCategory =
  | 'compliance'
  | 'risk'
  | 'missing_clause'
  | 'wording'
  | 'general'

export interface HighlightSpan {
  quote: string
  severity: Severity
  comment: string
}

export interface LegalReference {
  title: string
  article_ref: string | null
  quote: string
  doc_type: DocType
  similarity: number
}

export interface Recommendation {
  text: string
  category: RecommendationCategory
  quote?: string | null
  references: LegalReference[]
}

export interface Risk {
  text: string
  severity: RiskSeverity
  quote: string | null
}

export interface CaseLaw {
  case_number: string
  court: string
  date: string
  subject: string
  ruling: string
  relevance: string
  needs_verification: boolean
}

export interface AnalysisResult {
  summary: string
  recommendations: Recommendation[]
  risks: Risk[]
  highlights: HighlightSpan[]
  references: LegalReference[]
  case_law: CaseLaw[]
  llm_provider: string
}

export interface AnalysisResponse {
  id: number
  file_name: string
  status: 'pending' | 'completed' | 'failed'
  result: AnalysisResult | null
  document_text: string | null
  error: string | null
  created_at: string
}

export interface KnowledgeDocument {
  id: number
  title: string
  doc_type: DocType
  source_url: string | null
  file_name: string | null
  total_chunks: number
  created_at: string
}
