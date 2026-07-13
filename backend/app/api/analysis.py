"""Эндпоинты анализа документов юриста (Поток B)."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.embeddings import get_embedder
from app.core.llm.factory import get_llm_client
from app.core.rag import analyze_document, analyze_text
from app.db.database import get_session
from app.db.models import Analysis
from app.schemas.analysis import AnalysisResponse, AnalysisResult

router = APIRouter(prefix="/api/analyze", tags=["analysis"])

MAX_PDF_SIZE = 50 * 1024 * 1024  # 50 МБ

# Форматы, которые юристы могут загружать для анализа
ANALYSIS_ALLOWED_EXTENSIONS = (".pdf", ".docx", ".doc")


def _is_allowed_analysis_file(filename: str) -> bool:
    """Проверить расширение файла для анализа (PDF или DOCX)."""
    return filename.lower().endswith(ANALYSIS_ALLOWED_EXTENSIONS)


@router.post("", response_model=AnalysisResponse)
async def analyze_uploaded_document(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
) -> AnalysisResponse:
    """Загрузить PDF юриста для анализа и получить результат.

    Выполняется синхронно (для MVP). Для больших документов позже добавим
    фоновую очередь (Celery/RQ).
    """
    if not file.filename or not _is_allowed_analysis_file(file.filename):
        raise HTTPException(
            status_code=400,
            detail="Ожидается файл PDF, DOCX или DOC для анализа.",
        )

    file_bytes = await file.read()
    if len(file_bytes) == 0:
        raise HTTPException(status_code=400, detail="Файл пуст.")
    if len(file_bytes) > MAX_PDF_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"Файл слишком большой (макс. {MAX_PDF_SIZE//1024//1024} МБ).",
        )

    # Создаём запись со статусом pending
    record = Analysis(file_name=file.filename, status="pending")
    session.add(record)
    await session.commit()
    await session.refresh(record)

    try:
        result, document_text = await analyze_document(
            session,
            file_bytes=file_bytes,
            file_name=file.filename,
            llm_client=get_llm_client(),
            embedder=get_embedder(),
        )
        record.status = "completed"
        record.result_json = result.model_dump()
        record.document_text = document_text
        record.completed_at = datetime.now(timezone.utc)
        await session.commit()
        return AnalysisResponse(
            id=record.id,
            file_name=record.file_name,
            status=record.status,
            result=result,
            document_text=document_text,
            error=None,
            created_at=record.created_at.isoformat(),
        )
    except ValueError as exc:
        record.status = "failed"
        record.error = str(exc)
        await session.commit()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        record.status = "failed"
        record.error = f"Внутренняя ошибка: {exc}"
        await session.commit()
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/{analysis_id}", response_model=AnalysisResponse)
async def get_analysis(
    analysis_id: int,
    session: AsyncSession = Depends(get_session),
) -> AnalysisResponse:
    """Получить сохранённый результат анализа по id."""
    from sqlalchemy import select

    stmt = select(Analysis).where(Analysis.id == analysis_id)
    record = (await session.execute(stmt)).scalar_one_or_none()
    if record is None:
        raise HTTPException(status_code=404, detail="Анализ не найден.")

    result = (
        AnalysisResult.model_validate(record.result_json)
        if record.result_json
        else None
    )
    return AnalysisResponse(
        id=record.id,
        file_name=record.file_name,
        status=record.status,
        result=result,
        document_text=record.document_text,
        error=record.error,
        created_at=record.created_at.isoformat(),
    )


# ------------------------------------------------------------
#  Анализ текста напрямую (без файла) — для надстройки Word
# ------------------------------------------------------------


class AnalyzeTextRequest(BaseModel):
    """Запрос на анализ готового текста (от надстройки Word)."""

    text: str
    file_name: str = "document.docx"


@router.post("/text", response_model=AnalysisResponse)
async def analyze_text_endpoint(
    payload: AnalyzeTextRequest,
    session: AsyncSession = Depends(get_session),
) -> AnalysisResponse:
    """Проанализировать готовый текст (без загрузки файла).

    Используется надстройкой Word: текст берётся из открытого документа
    через Office.js и отправляется сюда.
    """
    if not payload.text.strip():
        raise HTTPException(status_code=400, detail="Текст документа пуст.")
    if len(payload.text) > 1_000_000:
        raise HTTPException(
            status_code=413, detail="Документ слишком большой (макс. 1М символов)."
        )

    record = Analysis(file_name=payload.file_name, status="pending")
    session.add(record)
    await session.commit()
    await session.refresh(record)

    try:
        result, document_text = await analyze_text(
            session,
            document_text=payload.text,
            file_name=payload.file_name,
            llm_client=get_llm_client(),
            embedder=get_embedder(),
        )
        record.status = "completed"
        record.result_json = result.model_dump()
        record.document_text = document_text
        record.completed_at = datetime.now(timezone.utc)
        await session.commit()
        return AnalysisResponse(
            id=record.id,
            file_name=record.file_name,
            status=record.status,
            result=result,
            document_text=document_text,
            error=None,
            created_at=record.created_at.isoformat(),
        )
    except ValueError as exc:
        record.status = "failed"
        record.error = str(exc)
        await session.commit()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        record.status = "failed"
        record.error = f"Внутренняя ошибка: {exc}"
        await session.commit()
        raise HTTPException(status_code=500, detail=str(exc)) from exc
