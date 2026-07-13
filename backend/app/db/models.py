"""ORM-модели таблиц.

SQLAlchemy-модели отражают структуру, созданную в migrations/init.sql.
Векторное поле `embedding` объявлено через тип из pgvector.

Важно: колонки объявлены через Column() с явным типом — это надёжнее, чем
сочетание Mapped[...] + mapped_column(...) при наличии векторного типа.
"""
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import foreign, relationship

from app.config import get_settings
from app.db.database import Base

settings = get_settings()


class KnowledgeDocument(Base):
    """Документ-источник права: кодекс, закон, судебная практика."""

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

    chunks = relationship(
        "DocumentChunk",
        primaryjoin="KnowledgeDocument.id == foreign(DocumentChunk.document_id)",
        back_populates="document",
        cascade="all, delete-orphan",
    )


class DocumentChunk(Base):
    """Чанк текста из источника права + его эмбеддинг."""

    __tablename__ = "document_chunks"

    id = Column(Integer, primary_key=True)
    document_id = Column(
        Integer,
        ForeignKey("knowledge_documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    chunk_index = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)
    article_ref = Column(Text)
    # Имя колонки в БД — "metadata" (зарезервированное слово обходим через явное имя)
    metadata_ = Column("metadata", JSONB, nullable=False, default=dict)
    embedding = Column(Vector(settings.embedding_dim), nullable=False)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    document = relationship(
        "KnowledgeDocument",
        primaryjoin="foreign(DocumentChunk.document_id) == KnowledgeDocument.id",
        back_populates="chunks",
    )

    __table_args__ = (UniqueConstraint("document_id", "chunk_index"),)


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
