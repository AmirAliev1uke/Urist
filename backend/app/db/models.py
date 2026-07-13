"""ORM-модели таблиц PostgreSQL.

PostgreSQL хранит только метаданные: источники права (knowledge_documents)
и результаты анализа (analyses). Векторы и тексты чанков хранятся в Qdrant.
"""
from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB

from app.db.database import Base


class KnowledgeDocument(Base):
    """Документ-источник права: кодекс, закон, судебная практика.

    Метаданные хранятся здесь, векторы чанков — в Qdrant (связь по document_id).
    """

    __tablename__ = "knowledge_documents"

    id = Column(Integer, primary_key=True)
    title = Column(Text, nullable=False)
    doc_type = Column(Text, nullable=False, default="other")
    source_url = Column(Text)
    file_name = Column(Text)
    total_chunks = Column(Integer, nullable=False, default=0, server_default="0")
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Analysis(Base):
    """Результат анализа загруженного юристом документа."""

    __tablename__ = "analyses"

    id = Column(Integer, primary_key=True)
    file_name = Column(Text, nullable=False)
    status = Column(String, nullable=False, default="pending", server_default="pending")
    document_text = Column(Text)
    result_json = Column(JSONB)
    error = Column(Text)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    completed_at = Column(DateTime(timezone=True))
