-- ============================================================
--  Начальная инициализация БД Legal AI Assistant (PostgreSQL)
--  PostgreSQL хранит только метаданные. Векторы — в Qdrant.
--  Выполняется автоматически при первом запуске контейнера БД.
-- ============================================================

-- ------------------------------------------------------------
--  Источник права (метаданные): ГК РФ, НК РФ, судебная практика
--  Векторы чанков хранятся в Qdrant, связь по document_id
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS knowledge_documents (
    id            SERIAL PRIMARY KEY,
    title         TEXT NOT NULL,
    doc_type      TEXT NOT NULL DEFAULT 'other',  -- code | judicial_practice | law | other
    source_url    TEXT,
    file_name     TEXT,
    total_chunks  INTEGER NOT NULL DEFAULT 0,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_knowledge_doc_type
    ON knowledge_documents(doc_type);
CREATE INDEX IF NOT EXISTS idx_knowledge_created_at
    ON knowledge_documents(created_at DESC);

-- ------------------------------------------------------------
--  Результаты анализа загруженных юристом документов
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS analyses (
    id            SERIAL PRIMARY KEY,
    file_name     TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'pending',  -- pending | completed | failed
    document_text TEXT,
    result_json   JSONB,
    error         TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at  TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_analyses_status ON analyses(status);
CREATE INDEX IF NOT EXISTS idx_analyses_created_at ON analyses(created_at DESC);
