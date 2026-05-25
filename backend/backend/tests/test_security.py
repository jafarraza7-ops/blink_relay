from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.core.security import (
    Role,
    UserClaims,
    _clear_jwks_cache,
    _get_jwks,
    get_current_user,
    get_optional_user,
    require_role,
    validate_token,
)


def test_role_enum_values():
    assert Role.REQUESTOR == "Requestor"
    assert Role.POD_REVIEWER == "PodReviewer"
    assert Role.PRODUCT_MANAGER == "ProductManager"
    assert Role.ADMIN == "Admin"
    assert Role.READ_ONLY == "ReadOnly"


def test_require_role_admin_bypass():
    admin = UserClaims(oid="oid", email="a@b.com", name="Admin", roles=[Role.ADMIN], tid="tid")
    dep = require_role(Role.PRODUCT_MANAGER)

    with patch("app.core.security.get_current_user", return_value=admin):
        result = dep(admin)
    assert result == admin


def test_require_role_matching_role():
    pm = UserClaims(oid="oid", email="pm@b.com", name="PM", roles=[Role.PRODUCT_MANAGER], tid="tid")
    dep = require_role(Role.PRODUCT_MANAGER)

    result = dep(pm)
    assert result == pm


def test_require_role_missing_role():
    requestor = UserClaims(oid="oid", email="r@b.com", name="R", roles=[Role.REQUESTOR], tid="tid")
    dep = require_role(Role.PRODUCT_MANAGER)

    with pytest.raises(HTTPException) as exc_info:
        dep(requestor)
    assert exc_info.value.status_code == 403


def test_validate_token_invalid_raises_401():
    with patch("app.core.security._get_jwks", return_value={}):
        with pytest.raises(HTTPException) as exc_info:
            validate_token("not.a.real.token")
        assert exc_info.value.status_code == 401


def test_validate_token_key_rotation_retry():
    """Simulates key rotation: first decode fails, cache cleared, second attempt also fails → 401."""
    from jose import JWTError

    call_count = [0]

    def mock_decode(token, jwks, **kwargs):
        call_count[0] += 1
        raise JWTError("invalid signature")

    with (
        patch("app.core.security._get_jwks", return_value={"keys": []}),
        patch("app.core.security.jwt.decode", side_effect=mock_decode),
        patch("app.core.security._clear_jwks_cache"),
    ):
        with pytest.raises(HTTPException):
            validate_token("header.payload.sig")

    assert call_count[0] == 2


def test_get_current_user_fallback_role():
    """If token has no roles claim, defaults to Requestor."""
    claims = {
        "oid": "test-oid",
        "preferred_username": "user@test.com",
        "name": "Test User",
        "tid": "test-tid",
    }
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="fake.token")

    with patch("app.core.security.validate_token", return_value=claims):
        user = get_current_user(credentials)

    assert Role.REQUESTOR in user.roles
    assert user.oid == "test-oid"


def test_get_current_user_with_roles():
    claims = {
        "oid": "pm-oid",
        "preferred_username": "pm@test.com",
        "name": "PM User",
        "tid": "tid",
        "roles": ["ProductManager"],
    }
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="fake.token")

    with patch("app.core.security.validate_token", return_value=claims):
        user = get_current_user(credentials)

    assert "ProductManager" in user.roles


def test_get_optional_user_no_credentials():
    result = get_optional_user(None)
    assert result is None


def test_get_optional_user_invalid_token():
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="bad.token")
    with patch("app.core.security.validate_token", side_effect=HTTPException(status_code=401, detail="invalid")):
        result = get_optional_user(credentials)
    assert result is None


def test_get_optional_user_valid():
    claims = {
        "oid": "some-oid",
        "preferred_username": "user@test.com",
        "name": "User",
        "tid": "tid",
    }
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="valid.token")
    with patch("app.core.security.validate_token", return_value=claims):
        result = get_optional_user(credentials)
    assert result is not None
    assert result.oid == "some-oid"
