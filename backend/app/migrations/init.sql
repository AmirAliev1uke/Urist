-- ============================================================
--  Начальная инициализация БД Legal AI Assistant
--  Выполняется автоматически при первом запуске контейнера БД
-- ============================================================

-- Расширение pgvector для хранения и поиска по эмбеддингам
CREATE EXTENSION IF NOT EXISTS vector;

-- ------------------------------------------------------------
--  Источник права в базе знаний (ГК РФ, НК РФ, судебная практика и т.д.)
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

-- ------------------------------------------------------------
--  Чанк текста из источника права + его вектор
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS document_chunks (
    id            SERIAL PRIMARY KEY,
    document_id   INTEGER NOT NULL REFERENCES knowledge_documents(id) ON DELETE CASCADE,
    chunk_index   INTEGER NOT NULL,
    text          TEXT NOT NULL,
    -- Метаданные для цитирования: номер статьи, раздел и т.п.
    article_ref   TEXT,
    metadata      JSONB NOT NULL DEFAULT '{}'::jsonb,
    embedding     vector(384) NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (document_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_chunks_document_id
    ON document_chunks(document_id);

-- Приближённый поиск ближайших соседей (HNSW) для быстрого similarity search.
-- cosine_distance = 1 - косинусное сходство.
CREATE INDEX IF NOT EXISTS idx_chunks_embedding_hnsw
    ON document_chunks
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

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
