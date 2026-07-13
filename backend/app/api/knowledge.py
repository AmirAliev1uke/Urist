"""Эндпоинты управления базой знаний (Поток A).

Загрузка PDF-источников права (ГК РФ, НК РФ, судебная практика) в pgvector.
"""
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.embeddings import get_embedder
from app.core.rag import ingest_document
from app.db.database import get_session
from app.db import vector_store

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])

ALLOWED_DOC_TYPES = {"code", "judicial_practice", "law", "other"}
MAX_PDF_SIZE = 50 * 1024 * 1024  # 50 МБ


class KnowledgeDocumentOut(BaseModel):
    """Сериализация источника права для API."""

    id: int
    title: str
    doc_type: str
    source_url: str | None
    file_name: str | None
    total_chunks: int
    created_at: str


@router.post("/upload", response_model=dict)
async def upload_knowledge_pdf(
    file: UploadFile = File(...),
    title: str = Form(...),
    doc_type: str = Form("other"),
    source_url: str | None = Form(None),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Загрузить PDF в базу знаний (закон, кодекс, судебная практика)."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Ожидается файл PDF.")

    if doc_type not in ALLOWED_DOC_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Недопустимый doc_type. Допустимо: {sorted(ALLOWED_DOC_TYPES)}",
        )

    file_bytes = await file.read()
    if len(file_bytes) == 0:
        raise HTTPException(status_code=400, detail="Файл пуст.")
    if len(file_bytes) > MAX_PDF_SIZE:
        raise HTTPException(
            status_code=413, detail=f"Файл слишком большой (макс. {MAX_PDF_SIZE//1024//1024} МБ)."
        )

    try:
        result = await ingest_document(
            session,
            file_bytes=file_bytes,
            title=title,
            doc_type=doc_type,
            source_url=source_url,
            file_name=file.filename,
            embedder=get_embedder(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return {
        "status": "ok",
        "message": (
            f"Документ «{title}» загружен, проиндексировано чанков: {result['chunks']}. "
            f"Авто-классификация: тип={result['doc_type']}, "
            f"год={result.get('year')}, суд={result.get('court_level')}"
        ),
        "chunks": result["chunks"],
        "classification": {
            "doc_type": result["doc_type"],
            "year": result.get("year"),
            "court_level": result.get("court_level"),
            "case_number": result.get("case_number"),
        },
        "document_id": result["document_id"],
    }


@router.get("/documents", response_model=list[KnowledgeDocumentOut])
async def list_documents(
    session: AsyncSession = Depends(get_session),
) -> list[KnowledgeDocumentOut]:
    """Список всех источников в базе знаний."""
    docs = await vector_store.list_documents(session)
    return [
        KnowledgeDocumentOut(
            id=d.id,
            title=d.title,
            doc_type=d.doc_type,
            source_url=d.source_url,
            file_name=d.file_name,
            total_chunks=d.total_chunks,
            created_at=d.created_at.isoformat(),
        )
        for d in docs
    ]


@router.delete("/documents/{document_id}")
async def delete_document(
    document_id: int,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Удалить источник и все его чанки."""
    deleted = await vector_store.delete_document(session, document_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Документ не найден.")
    await session.commit()
    return {"status": "ok", "message": f"Документ {document_id} удалён."}
