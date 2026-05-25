from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import logging

from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import UserClaims, get_current_user
from app.models.request import Attachment, Request
from app.services.storage_service import StorageService, StorageError

logger = logging.getLogger(__name__)

router = APIRouter(tags=["files"])

ALLOWED_CONTENT_TYPES = {
    "image/png", "image/jpeg", "image/gif", "image/webp",
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "text/plain", "text/csv",
}
MAX_FILE_SIZE = 25 * 1024 * 1024  # 25 MB
MAX_FILES_PER_REQUEST = 5


class AttachmentResponse(BaseModel):
    id: uuid.UUID
    request_id: uuid.UUID
    filename: str
    content_type: str
    size_bytes: int
    created_at: datetime
    download_url: str | None = None

    model_config = {"from_attributes": True}


@router.get("/requests/{request_id}/files", response_model=list[AttachmentResponse])
async def list_files(
    request_id: uuid.UUID,
    user: Annotated[UserClaims, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[AttachmentResponse]:
    req = await db.get(Request, request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")

    result = await db.execute(
        select(Attachment).where(Attachment.request_id == request_id).order_by(Attachment.created_at)
    )
    attachments = result.scalars().all()
    storage = StorageService()
    responses = []
    for a in attachments:
        try:
            url = storage.generate_sas_url(a.blob_name)
        except StorageError:
            url = None
        responses.append(
            AttachmentResponse(
                id=a.id,
                request_id=a.request_id,
                filename=a.filename,
                content_type=a.content_type,
                size_bytes=a.size_bytes,
                created_at=a.created_at,
                download_url=url,
            )
        )
    return responses


@router.post(
    "/requests/{request_id}/files",
    response_model=list[AttachmentResponse],
    status_code=status.HTTP_201_CREATED,
)
async def upload_files(
    request_id: uuid.UUID,
    files: Annotated[list[UploadFile], File(...)],
    user: Annotated[UserClaims, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[AttachmentResponse]:
    req = await db.get(Request, request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")

    if len(files) > MAX_FILES_PER_REQUEST:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Maximum {MAX_FILES_PER_REQUEST} files per upload",
        )

    storage = StorageService()
    created: list[AttachmentResponse] = []

    for file in files:
        if file.content_type not in ALLOWED_CONTENT_TYPES:
            raise HTTPException(
                status_code=415, detail=f"Unsupported file type: {file.content_type}"
            )

        contents = await file.read()
        if len(contents) > MAX_FILE_SIZE:
            raise HTTPException(status_code=413, detail=f"File '{file.filename}' exceeds 25 MB")

        blob_name = f"{request_id}/{uuid.uuid4()}_{file.filename}"
        try:
            await storage.upload_bytes(blob_name, contents, file.content_type or "application/octet-stream")
        except StorageError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

        attachment = Attachment(
            request_id=request_id,
            filename=file.filename or "unnamed",
            content_type=file.content_type or "application/octet-stream",
            blob_name=blob_name,
            size_bytes=len(contents),
            uploaded_by_oid=user.oid,
        )
        db.add(attachment)
        await db.flush()
        await db.refresh(attachment)

        try:
            url = storage.generate_sas_url(blob_name)
        except StorageError:
            url = None

        created.append(
            AttachmentResponse(
                id=attachment.id,
                request_id=attachment.request_id,
                filename=attachment.filename,
                content_type=attachment.content_type,
                size_bytes=attachment.size_bytes,
                created_at=attachment.created_at,
                download_url=url,
            )
        )

    await db.commit()

    # If Jira or JSM tickets already exist, sync the newly uploaded files there.
    if req.jira_ticket_key or req.jsm_ticket_key:
        new_ids = [str(a.id) for a in created]
        try:
            from app.workers.tasks import task_sync_attachments
            task_sync_attachments.delay(str(request_id), new_ids)
        except Exception:
            logger.warning("task_sync_attachments raised in eager mode — non-fatal", exc_info=True)

    return created


# ── Local-filesystem fallback download route ─────────────────────────────────
# Only useful when StorageService is in local-filesystem mode (no Azure
# connection string in dev). In production this route still exists but the
# directory is empty, so it returns 404 — no security risk.

@router.get("/local-uploads/{blob_path:path}")
async def download_local_blob(blob_path: str):
    settings = get_settings()
    if not settings.is_local:
        raise HTTPException(status_code=404, detail="Not found")

    base = StorageService.local_uploads_dir()
    target = (base / blob_path).resolve()
    # Defence in depth — refuse to serve anything outside the uploads directory
    try:
        target.relative_to(base)
    except ValueError:
        raise HTTPException(status_code=403, detail="Forbidden") from None

    if not target.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(target)
