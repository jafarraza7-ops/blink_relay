from __future__ import annotations

import io
import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.request import Attachment, Pod, Request, RequestStatus, RequestType, Severity


async def _make_request(db: AsyncSession) -> Request:
    req = Request(
        id=uuid.uuid4(),
        title="Files test",
        request_type=RequestType.FEATURE,
        pod=Pod.DATA,
        severity=Severity.LOW,
        status=RequestStatus.SUBMITTED,
        business_problem="File testing",
        affected_area="Data pipeline",
        submitter_oid="files-oid",
        submitter_email="files@test.com",
        submitter_name="Files Tester",
    )
    db.add(req)
    await db.flush()
    await db.refresh(req)
    return req


@pytest.mark.asyncio
async def test_list_files_empty(authed_client: AsyncClient, db_session: AsyncSession):
    req = await _make_request(db_session)
    with patch("app.api.files.StorageService") as mock_cls:
        mock_cls.return_value.generate_sas_url.return_value = "https://blob/file?sas"
        resp = await authed_client.get(f"/api/requests/{req.id}/files")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_files_with_attachments(authed_client: AsyncClient, db_session: AsyncSession):
    req = await _make_request(db_session)
    attachment = Attachment(
        id=uuid.uuid4(),
        request_id=req.id,
        filename="test.pdf",
        content_type="application/pdf",
        blob_name=f"{req.id}/test.pdf",
        size_bytes=1024,
        uploaded_by_oid="files-oid",
    )
    db_session.add(attachment)
    await db_session.flush()

    with patch("app.api.files.StorageService") as mock_cls:
        mock_cls.return_value.generate_sas_url.return_value = "https://blob/test.pdf?sas"
        resp = await authed_client.get(f"/api/requests/{req.id}/files")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["filename"] == "test.pdf"
    assert data[0]["download_url"] == "https://blob/test.pdf?sas"


@pytest.mark.asyncio
async def test_list_files_request_not_found(authed_client: AsyncClient):
    with patch("app.api.files.StorageService"):
        resp = await authed_client.get("/api/requests/00000000-0000-0000-0000-000000000000/files")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_upload_file_success(authed_client: AsyncClient, db_session: AsyncSession):
    req = await _make_request(db_session)

    with patch("app.api.files.StorageService") as mock_cls:
        storage = MagicMock()
        storage.upload_bytes = AsyncMock(return_value="blob-name")
        storage.generate_sas_url.return_value = "https://blob/uploaded.png?sas"
        mock_cls.return_value = storage

        resp = await authed_client.post(
            f"/api/requests/{req.id}/files",
            files=[("files", ("test.png", io.BytesIO(b"PNG_DATA"), "image/png"))],
        )

    assert resp.status_code == 201
    data = resp.json()
    assert len(data) == 1
    assert data[0]["filename"] == "test.png"
    assert data[0]["content_type"] == "image/png"


@pytest.mark.asyncio
async def test_upload_file_unsupported_type(authed_client: AsyncClient, db_session: AsyncSession):
    req = await _make_request(db_session)

    with patch("app.api.files.StorageService"):
        resp = await authed_client.post(
            f"/api/requests/{req.id}/files",
            files=[("files", ("test.exe", io.BytesIO(b"EXE"), "application/x-msdownload"))],
        )
    assert resp.status_code == 415


@pytest.mark.asyncio
async def test_upload_too_many_files(authed_client: AsyncClient, db_session: AsyncSession):
    req = await _make_request(db_session)

    with patch("app.api.files.StorageService"):
        files = [
            ("files", (f"file{i}.png", io.BytesIO(b"PNG"), "image/png"))
            for i in range(6)
        ]
        resp = await authed_client.post(f"/api/requests/{req.id}/files", files=files)
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_upload_file_request_not_found(authed_client: AsyncClient):
    with patch("app.api.files.StorageService"):
        resp = await authed_client.post(
            "/api/requests/00000000-0000-0000-0000-000000000000/files",
            files=[("files", ("test.png", io.BytesIO(b"PNG"), "image/png"))],
        )
    assert resp.status_code == 404
