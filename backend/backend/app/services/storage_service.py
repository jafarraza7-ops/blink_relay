from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone
from functools import partial
from pathlib import Path

from azure.storage.blob import (
    BlobSasPermissions,
    BlobServiceClient,
    generate_blob_sas,
)
from fastapi import UploadFile

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class StorageError(Exception):
    pass


# Path under which the local-filesystem backend writes uploaded blobs in dev.
# Resolved relative to the backend working directory so tests + uvicorn agree.
_LOCAL_UPLOADS_DIR = Path(os.getenv("LOCAL_UPLOADS_DIR", "local_uploads")).resolve()


class _LocalFilesystemBackend:
    """Drop-in replacement for the Azure SDK calls when no connection string
    is configured. Writes blobs to disk under ``LOCAL_UPLOADS_DIR`` and
    returns a relative URL the frontend can hit via the local files route.
    """

    def __init__(self, base_dir: Path) -> None:
        self._base = base_dir
        self._base.mkdir(parents=True, exist_ok=True)

    def write_bytes(self, blob_name: str, data: bytes) -> Path:
        target = self._base / blob_name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return target

    def delete(self, blob_name: str) -> None:
        target = self._base / blob_name
        if target.exists():
            target.unlink()

    def url_for(self, blob_name: str) -> str:
        # Served by ``GET /api/local-uploads/{path}`` (dev only). The route is
        # mounted from main.py when no Azure storage is configured.
        return f"/api/local-uploads/{blob_name}"


class StorageService:
    """Blob storage facade.

    Uses Azure Blob Storage when ``AZURE_STORAGE_CONNECTION_STRING`` is set.
    In local dev with no connection string, falls back to a filesystem backend
    so attachments work without configuring Azure. Production/staging without
    a connection string still raises loudly via ``StorageError`` on first use.
    """

    def __init__(self) -> None:
        self._container = settings.AZURE_STORAGE_CONTAINER
        self._client: BlobServiceClient | None = None
        self._local: _LocalFilesystemBackend | None = None

        conn_str = settings.AZURE_STORAGE_CONNECTION_STRING
        if conn_str:
            try:
                self._client = BlobServiceClient.from_connection_string(conn_str)
            except Exception as exc:
                if settings.is_local:
                    logger.warning(
                        "Invalid AZURE_STORAGE_CONNECTION_STRING in local env "
                        "(%s) — falling back to local filesystem at %s",
                        exc, _LOCAL_UPLOADS_DIR,
                    )
                    self._local = _LocalFilesystemBackend(_LOCAL_UPLOADS_DIR)
                else:
                    raise StorageError(f"Invalid storage connection string: {exc}") from exc
        elif settings.is_local:
            logger.warning(
                "AZURE_STORAGE_CONNECTION_STRING not set — falling back to "
                "local filesystem at %s. Set the connection string to use "
                "real Azure Blob Storage.", _LOCAL_UPLOADS_DIR,
            )
            self._local = _LocalFilesystemBackend(_LOCAL_UPLOADS_DIR)
        else:
            raise StorageError(
                "AZURE_STORAGE_CONNECTION_STRING must be set in non-local environments"
            )

    async def upload_file(self, file: UploadFile, request_id: str) -> tuple[str, int]:
        """Upload a FastAPI UploadFile and return (blob_name, size_bytes)."""
        import uuid as _uuid
        contents = await file.read()
        blob_name = f"{request_id}/{_uuid.uuid4()}_{file.filename}"
        await self.upload_bytes(blob_name, contents, file.content_type or "application/octet-stream")
        return blob_name, len(contents)

    async def upload_bytes(self, blob_name: str, data: bytes, content_type: str) -> str:
        try:
            if self._local is not None:
                # Filesystem write is fast — no need for the executor.
                self._local.write_bytes(blob_name, data)
                logger.info("Uploaded local blob: %s (%d bytes)", blob_name, len(data))
                return blob_name

            assert self._client is not None  # narrow for type-checkers
            loop = asyncio.get_event_loop()
            container_client = self._client.get_container_client(self._container)
            blob_client = container_client.get_blob_client(blob_name)
            fn = partial(
                blob_client.upload_blob,
                data,
                overwrite=True,
                content_settings={"content_type": content_type},
            )
            await loop.run_in_executor(None, fn)
            logger.info("Uploaded blob: %s (%d bytes)", blob_name, len(data))
            return blob_name
        except StorageError:
            raise
        except Exception as exc:
            raise StorageError(f"Failed to upload {blob_name}: {exc}") from exc

    def generate_sas_url(self, blob_name: str, expiry_minutes: int = 15) -> str:
        try:
            if self._local is not None:
                return self._local.url_for(blob_name)

            assert self._client is not None
            account_name = self._client.account_name
            account_key = self._client.credential.account_key
            sas_token = generate_blob_sas(
                account_name=account_name,
                container_name=self._container,
                blob_name=blob_name,
                account_key=account_key,
                permission=BlobSasPermissions(read=True),
                expiry=datetime.now(timezone.utc) + timedelta(minutes=expiry_minutes),
            )
            return f"https://{account_name}.blob.core.windows.net/{self._container}/{blob_name}?{sas_token}"
        except StorageError:
            raise
        except Exception as exc:
            raise StorageError(f"Failed to generate SAS URL for {blob_name}: {exc}") from exc

    async def download_bytes(self, blob_name: str) -> bytes:
        """Download a blob and return its raw bytes."""
        try:
            if self._local is not None:
                target = self._local._base / blob_name
                if not target.exists():
                    raise StorageError(f"Local blob not found: {blob_name}")
                return target.read_bytes()

            assert self._client is not None
            loop = asyncio.get_event_loop()
            container_client = self._client.get_container_client(self._container)
            blob_client = container_client.get_blob_client(blob_name)
            downloader = await loop.run_in_executor(None, blob_client.download_blob)
            return await loop.run_in_executor(None, downloader.readall)
        except StorageError:
            raise
        except Exception as exc:
            raise StorageError(f"Failed to download {blob_name}: {exc}") from exc

    async def delete_file(self, blob_name: str) -> None:
        try:
            if self._local is not None:
                self._local.delete(blob_name)
                logger.info("Deleted local blob: %s", blob_name)
                return

            assert self._client is not None
            loop = asyncio.get_event_loop()
            container_client = self._client.get_container_client(self._container)
            fn = partial(container_client.delete_blob, blob_name, delete_snapshots="include")
            await loop.run_in_executor(None, fn)
            logger.info("Deleted blob: %s", blob_name)
        except StorageError:
            raise
        except Exception as exc:
            raise StorageError(f"Failed to delete {blob_name}: {exc}") from exc

    @staticmethod
    def local_uploads_dir() -> Path:
        """Return the resolved local filesystem path used for fallback uploads.

        Used by the GET /api/local-uploads/{path} route in main.py so it can
        serve uploaded files in dev without exposing the wider filesystem.
        """
        return _LOCAL_UPLOADS_DIR
