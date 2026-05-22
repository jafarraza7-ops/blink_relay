from __future__ import annotations

import os

# Set env vars BEFORE any app imports to avoid cold-start failures
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("AZURE_TENANT_ID", "test-tenant")
os.environ.setdefault("AZURE_CLIENT_ID", "test-client")
os.environ.setdefault("AZURE_CLIENT_SECRET", "test-secret")
os.environ.setdefault("JIRA_EMAIL", "test@test.com")
os.environ.setdefault("JIRA_API_TOKEN", "test-token")
os.environ.setdefault("AZURE_STORAGE_CONNECTION_STRING", "DefaultEndpointsProtocol=https;AccountName=test;AccountKey=dGVzdA==;EndpointSuffix=core.windows.net")
# JSM uses mock mode in tests so JsmService never hits the network. JIRA_MOCK
# and SKIP_AUTH are force-overridden because the developer's local .env may
# enable them — tests must run against a known baseline regardless of dev env.
os.environ["JSM_MOCK"] = "true"
os.environ["JSM_PROJECT_KEY"] = "BLR"
os.environ["JIRA_MOCK"] = "false"
os.environ["SKIP_AUTH"] = "false"

# Clear settings cache so our env vars take effect
from app.core.config import get_settings
get_settings.cache_clear()

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.security import UserClaims, Role
from app.models.request import (  # noqa: F401 – ensure all models are registered
    ALLOWED_TRANSITIONS, Attachment, AuditLog, Message, Pod, Request,
    RequestStatus, RequestType, Severity, User,
)

# ── SQLite in-memory test database ────────────────────────────────────────────

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(TEST_DB_URL, echo=False)
TestSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)

# We need Base after the models are imported
from app.core.database import Base, get_db


@pytest.fixture(scope="session", autouse=True)
async def create_test_tables():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def db_session():
    async with TestSessionLocal() as session:
        yield session
        await session.rollback()


# ── FastAPI test app (no lifespan) ─────────────────────────────────────────────

@pytest.fixture
def app(db_session: AsyncSession):
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    from app.api import auth, files, health, requests, thread, webhook, workflow

    _app = FastAPI()
    _app.add_middleware(
        CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
    )
    _app.include_router(auth.router, prefix="/api")
    _app.include_router(requests.router, prefix="/api")
    _app.include_router(workflow.router, prefix="/api")
    _app.include_router(thread.router, prefix="/api")
    _app.include_router(files.router, prefix="/api")
    _app.include_router(webhook.router, prefix="/api")
    _app.include_router(health.router)

    async def _override_db():
        yield db_session

    _app.dependency_overrides[get_db] = _override_db
    return _app


# ── User fixtures ─────────────────────────────────────────────────────────────

def _make_user(role: str = Role.REQUESTOR) -> UserClaims:
    return UserClaims(
        oid="test-oid-1234",
        email="testuser@blinkcharging.com",
        name="Test User",
        roles=[role],
        tid="test-tenant-id",
    )


@pytest.fixture
def reviewer_user() -> UserClaims:
    return _make_user(Role.POD_REVIEWER)


@pytest.fixture
def pm_user() -> UserClaims:
    return _make_user(Role.PRODUCT_MANAGER)


@pytest.fixture
def requestor_user() -> UserClaims:
    return _make_user(Role.REQUESTOR)


# ── Authenticated clients ──────────────────────────────────────────────────────

@pytest.fixture
async def authed_client(app, requestor_user):
    from app.core.security import get_current_user, get_optional_user

    app.dependency_overrides[get_current_user] = lambda: requestor_user
    app.dependency_overrides[get_optional_user] = lambda: requestor_user

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c

    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_optional_user, None)


@pytest.fixture
async def reviewer_client(app, reviewer_user):
    from app.core.security import get_current_user, get_optional_user

    app.dependency_overrides[get_current_user] = lambda: reviewer_user
    app.dependency_overrides[get_optional_user] = lambda: reviewer_user

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c

    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_optional_user, None)


@pytest.fixture
async def pm_client(app, pm_user):
    from app.core.security import get_current_user, get_optional_user

    app.dependency_overrides[get_current_user] = lambda: pm_user
    app.dependency_overrides[get_optional_user] = lambda: pm_user

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c

    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_optional_user, None)


@pytest.fixture
async def anon_client(app):
    from app.core.security import get_optional_user

    app.dependency_overrides[get_optional_user] = lambda: None

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c

    app.dependency_overrides.pop(get_optional_user, None)


# ── Auto-mock Celery tasks ─────────────────────────────────────────────────────
#
# Default-mock the side-effect-heavy tasks so plain unit tests never accidentally
# fire real notifications or hit external services. Tests that *want* to observe
# the JSM/Jira flow opt in via the ``jsm_task_spies`` fixture below, which yields
# the patched MagicMocks.

@pytest.fixture(autouse=True)
def mock_celery_tasks():
    with (
        patch("app.workers.tasks.task_send_status_notification.delay", MagicMock()),
        patch("app.workers.tasks.task_create_jira_ticket.delay", MagicMock()),
        patch("app.workers.tasks.route_request_to_pod.delay", MagicMock()),
        patch("app.workers.tasks.task_create_jsm_ticket.delay", MagicMock()),
        patch("app.workers.tasks.task_jsm_add_comment.delay", MagicMock()),
        patch("app.workers.tasks.task_close_jsm_ticket.delay", MagicMock()),
    ):
        yield


@pytest.fixture
def jsm_task_spies():
    """Per-test spies for the JSM task ``.delay()`` entry points.

    Yields a dict of MagicMocks that capture every call made during the test —
    use ``spies["create"].assert_called_once_with(...)``  etc. to assert on the
    expected JSM workflow without enabling real Celery execution.
    """
    spies = {
        "create": MagicMock(name="task_create_jsm_ticket.delay"),
        "comment": MagicMock(name="task_jsm_add_comment.delay"),
        "close": MagicMock(name="task_close_jsm_ticket.delay"),
        "create_jira": MagicMock(name="task_create_jira_ticket.delay"),
    }
    with (
        patch("app.workers.tasks.task_create_jsm_ticket.delay", spies["create"]),
        patch("app.workers.tasks.task_jsm_add_comment.delay", spies["comment"]),
        patch("app.workers.tasks.task_close_jsm_ticket.delay", spies["close"]),
        patch("app.workers.tasks.task_create_jira_ticket.delay", spies["create_jira"]),
        patch("app.api.requests.task_create_jsm_ticket", spies["create"]),
        patch("app.api.thread.task_jsm_add_comment", spies["comment"]),
        patch("app.api.workflow.task_jsm_add_comment", spies["comment"]),
        patch("app.api.workflow.task_close_jsm_ticket", spies["close"]),
        patch("app.api.workflow.task_create_jira_ticket", spies["create_jira"]),
        patch("app.api.webhook.task_close_jsm_ticket", spies["close"]),
    ):
        # Make the patched module-level objects look like Celery tasks: every
        # spy needs a ``.delay`` that defers to the spy itself, since call sites
        # invoke ``task_create_jsm_ticket.delay(...)``.
        for spy in (spies["create"], spies["comment"], spies["close"], spies["create_jira"]):
            spy.delay = spy
        yield spies


# ── Sample request payload ─────────────────────────────────────────────────────

@pytest.fixture
def sample_request_payload():
    return {
        "title": "Add EV charging session history export",
        "request_type": "Feature",
        "pod": "Driver",
        "severity": "Medium",
        "business_problem": "Drivers need to export their charging history for expense reporting purposes.",
        "affected_area": "Driver app — My Sessions screen",
        "expected_outcome": "A CSV export button on the sessions screen.",
    }
