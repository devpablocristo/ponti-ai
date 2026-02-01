import os

import pytest
from fastapi import HTTPException

from adapters.inbound.api.auth.headers import require_headers
from adapters.outbound.security import api_keys


def test_auth_missing_headers() -> None:
    with pytest.raises(HTTPException) as exc:
        require_headers(x_api_key=None, x_user_id="1", x_project_id="p1")
    assert exc.value.status_code == 401


def test_auth_invalid_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_API_KEYS", "k1,k2")
    api_keys._load_keys.cache_clear()
    with pytest.raises(HTTPException) as exc:
        require_headers(x_api_key="bad", x_user_id="1", x_project_id="p1")
    assert exc.value.status_code == 403


def test_auth_valid_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_API_KEYS", "k1,k2")
    api_keys._load_keys.cache_clear()
    ctx = require_headers(x_api_key="k1", x_user_id="1", x_project_id="p1")
    assert ctx.project_id == "p1"
