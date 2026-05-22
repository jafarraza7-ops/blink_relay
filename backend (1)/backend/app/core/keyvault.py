from __future__ import annotations

import logging

from azure.core.exceptions import ResourceNotFoundError
from azure.identity import DefaultAzureCredential, ManagedIdentityCredential
from azure.keyvault.secrets import SecretClient

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_client: SecretClient | None = None


def get_kv_client() -> SecretClient | None:
    global _client
    if _client is not None:
        return _client
    if not settings.AZURE_KEY_VAULT_URI:
        return None
    credential = (
        ManagedIdentityCredential()
        if settings.ENVIRONMENT in ("staging", "production")
        else DefaultAzureCredential()
    )
    _client = SecretClient(vault_url=settings.AZURE_KEY_VAULT_URI, credential=credential)
    return _client


def get_secret(name: str, default: str = "") -> str:
    client = get_kv_client()
    if client is None:
        return default
    try:
        return client.get_secret(name).value or default
    except ResourceNotFoundError:
        logger.warning("Key Vault secret '%s' not found", name)
        return default
    except Exception:
        logger.exception("Error fetching Key Vault secret '%s'", name)
        return default


def set_secret(name: str, value: str) -> None:
    client = get_kv_client()
    if client is None:
        raise RuntimeError("Key Vault client not initialised")
    client.set_secret(name, value)
