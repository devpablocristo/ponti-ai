from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from src.api.deps import _allowed_service_keys, require_headers


def _fake_request(keys: str):
    settings = SimpleNamespace(ai_service_keys=keys)
    container = SimpleNamespace(settings=settings)
    app = SimpleNamespace(state=SimpleNamespace(container=container))
    return SimpleNamespace(app=app)


def test_allowed_service_keys_parses_csv() -> None:
    request = _fake_request(" key-1, key-2 ,,key-3 ")
    assert _allowed_service_keys(request.app.state.container.settings) == {"key-1", "key-2", "key-3"}


def test_require_headers_accepts_valid_service_key() -> None:
    auth = require_headers(
        request=_fake_request("svc-1,svc-2"),
        x_user_id="user-1",
        x_project_id="project-1",
        x_service_key="svc-2",
    )
    assert auth.actor == "user-1"
    assert auth.tenant_id == "project-1"


@pytest.mark.parametrize("service_key", ["", "missing", " svc-9 "])
def test_require_headers_rejects_invalid_or_missing_service_key(service_key: str) -> None:
    with pytest.raises(HTTPException) as excinfo:
        require_headers(
            request=_fake_request("svc-1,svc-2"),
            x_user_id="user-1",
            x_project_id="project-1",
            x_service_key=service_key,
        )
    assert excinfo.value.status_code == 401
