from __future__ import annotations

import logging
from functools import lru_cache
from typing import Literal

from azure.core.exceptions import ResourceNotFoundError
from azure.identity import DefaultAzureCredential, ManagedIdentityCredential
from azure.keyvault.secrets import SecretClient
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

# Secrets that must be pulled from Key Vault in non-local environments.
# The Key Vault secret name maps to the settings field name (upper-cased, underscores
# replaced with hyphens to match the naming convention used during provisioning).
_KV_SECRET_FIELDS = {
    "DATABASE_URL": "DATABASE-URL",
    "REDIS_URL": "REDIS-URL",
    "AZURE_STORAGE_CONNECTION_STRING": "AZURE-STORAGE-CONNECTION-STRING",
    "APP_CONFIG_CONNECTION_STRING": "APP-CONFIG-CONNECTION-STRING",
    "JIRA_API_TOKEN": "JIRA-API-TOKEN",
    "JIRA_WEBHOOK_SECRET": "JIRA-WEBHOOK-SECRET",
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # ── Application ──────────────────────────────────────────────────────────
    ENVIRONMENT: Literal["local", "staging", "production"] = "local"
    APP_VERSION: str = "1.0.0"
    FRONTEND_URL: str = "http://localhost:5173"

    # ── Local dev overrides ───────────────────────────────────────────────────
    SKIP_AUTH: bool = False               # bypass JWT validation; returns mock user
    SKIP_AUTH_AS: Literal["admin", "pm", "requestor"] = "admin"  # role for mock user when SKIP_AUTH=True
    JIRA_MOCK: bool = False               # return fake Jira ticket data without calling API
    JSM_MOCK: bool = False                # return fake JSM data without calling Service Desk API
    CELERY_TASK_ALWAYS_EAGER: bool = False  # run Celery tasks inline (no broker needed)

    # ── Email backend ─────────────────────────────────────────────────────────
    # Use "smtp" for local dev with Ethereal; "graph" for production (Microsoft Graph API)
    EMAIL_BACKEND: Literal["graph", "smtp"] = "smtp"
    SMTP_HOST: str = "smtp.ethereal.email"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""   # Ethereal username — get from https://ethereal.email/create
    SMTP_PASS: str = ""   # Ethereal password
    SMTP_FROM: str = ""   # Displayed as the sender; defaults to SMTP_USER if blank

    # ── Database ─────────────────────────────────────────────────────────────
    DATABASE_URL: str = ""

    # ── Redis ─────────────────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"

    # ── Entra ID ─────────────────────────────────────────────────────────────
    AZURE_TENANT_ID: str = ""
    AZURE_CLIENT_ID: str = ""
    AZURE_CLIENT_SECRET: str = ""  # local dev only; prod uses MI

    # ── Azure Storage ─────────────────────────────────────────────────────────
    AZURE_STORAGE_CONNECTION_STRING: str = ""
    AZURE_STORAGE_CONTAINER: str = "attachments"

    # ── Key Vault ─────────────────────────────────────────────────────────────
    AZURE_KEY_VAULT_URI: str = ""

    # ── App Configuration ─────────────────────────────────────────────────────
    APP_CONFIG_CONNECTION_STRING: str = ""

    # ── Application Insights ──────────────────────────────────────────────────
    APPINSIGHTS_CONNECTION_STRING: str = ""

    # ── Jira ─────────────────────────────────────────────────────────────────
    JIRA_BASE_URL: str = "https://blinkcharging.atlassian.net"
    JIRA_EMAIL: str = ""
    JIRA_API_TOKEN: str = ""
    JIRA_WEBHOOK_SECRET: str = ""
    JIRA_DEFAULT_ASSIGNEE_ACCOUNT_ID: str = ""
    JIRA_PROJECT_CHARGER: str = "REL"
    JIRA_PROJECT_DRIVER: str = "REL"
    JIRA_PROJECT_REVENUE: str = "REL"
    JIRA_PROJECT_DATA: str = "REL"
    JIRA_PROJECT_DEVOPS: str = "REL"
    JIRA_PROJECT_DENALI: str = "REL"

    # ── Jira Service Management (JSM) ─────────────────────────────────────────
    # Service desk that holds the customer-facing ticket for every Blink Relay
    # request. Authenticates with the same Atlassian credentials as Jira Software.
    JSM_BASE_URL: str = ""                # defaults to JIRA_BASE_URL when blank
    JSM_PROJECT_KEY: str = "BLR"          # JSM project key (e.g. BLR for Blink Relay)
    JSM_SERVICE_DESK_ID: str = ""         # numeric ID — required for /servicedeskapi calls
    JSM_REQUEST_TYPE_ID: str = ""         # numeric ID for "Tech Request" request type
    JSM_RESOLVE_TRANSITION: str = "Resolve"  # transition name when closing JSM ticket
    JSM_WAITING_ON_CUSTOMER_TRANSITION: str = "Wait for customer"

    # ── Graph / Teams ─────────────────────────────────────────────────────────
    GRAPH_API_BASE_URL: str = "https://graph.microsoft.com/v1.0"
    TEAMS_WEBHOOK_URL: str = ""

    @field_validator("DATABASE_URL")
    @classmethod
    def _coerce_db_url(cls, v: str) -> str:
        # Normalise postgres:// → postgresql+asyncpg:// for SQLAlchemy async
        if v.startswith("postgres://"):
            v = v.replace("postgres://", "postgresql+asyncpg://", 1)
        if v.startswith("postgresql://") and "+asyncpg" not in v:
            v = v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v

    @property
    def is_local(self) -> bool:
        return self.ENVIRONMENT == "local"

    @property
    def jira_project_map(self) -> dict[str, str]:
        return {
            "Charger": self.JIRA_PROJECT_CHARGER,
            "Driver": self.JIRA_PROJECT_DRIVER,
            "Revenue": self.JIRA_PROJECT_REVENUE,
            "Data": self.JIRA_PROJECT_DATA,
            "DevOps": self.JIRA_PROJECT_DEVOPS,
            "Denali": self.JIRA_PROJECT_DENALI,
        }


def _load_from_key_vault(settings: Settings) -> Settings:
    """Override secret fields from Azure Key Vault using Managed Identity.

    Called at startup in staging/production. Uses DefaultAzureCredential which
    resolves to Managed Identity when running in App Service, and falls back to
    az CLI credentials locally (if AZURE_KEY_VAULT_URI is set).
    """
    if not settings.AZURE_KEY_VAULT_URI:
        logger.warning("AZURE_KEY_VAULT_URI not set — skipping Key Vault secret load")
        return settings

    try:
        credential = (
            ManagedIdentityCredential()
            if settings.ENVIRONMENT in ("staging", "production")
            else DefaultAzureCredential()
        )
        client = SecretClient(vault_url=settings.AZURE_KEY_VAULT_URI, credential=credential)

        overrides: dict[str, str] = {}
        for field_name, secret_name in _KV_SECRET_FIELDS.items():
            try:
                secret = client.get_secret(secret_name)
                if secret.value:
                    overrides[field_name] = secret.value
                    logger.info("Loaded secret %s from Key Vault", secret_name)
            except ResourceNotFoundError:
                logger.warning("Key Vault secret %s not found — using env value", secret_name)

        if overrides:
            # Re-instantiate with overrides applied on top of current values
            current = settings.model_dump()
            current.update(overrides)
            settings = Settings.model_validate(current)

    except Exception:
        logger.exception("Failed to load secrets from Key Vault — using environment values")

    return settings


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    if not settings.is_local:
        settings = _load_from_key_vault(settings)
    return settings
