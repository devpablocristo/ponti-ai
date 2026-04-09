"""Cliente HTTP async hacia ponti-backend (lecturas para el asistente)."""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlencode

import httpx

from app.config import Settings


class PontiBackendClient:
    """Proxy de lectura con auth por API key + usuario (mismo patrón que el BFF)."""

    def __init__(self, settings: Settings) -> None:
        raw_base = str(getattr(settings, "ponti_backend_base_url", "") or "").strip().rstrip("/")
        self._base = raw_base
        self._api_key = str(getattr(settings, "ponti_backend_api_key", "") or "").strip()
        self._auth_extra = str(getattr(settings, "ponti_backend_authorization", "") or "").strip()
        self._timeout = max(1.0, float(getattr(settings, "ponti_backend_timeout_ms", 15000) or 15000) / 1000.0)
        self._max_chars = max(2000, int(getattr(settings, "ponti_backend_max_response_chars", 16000) or 16000))

    def is_configured(self) -> bool:
        return bool(self._base and self._api_key)

    def _clip(self, payload: Any) -> dict[str, Any]:
        try:
            text = json.dumps(payload, ensure_ascii=False, default=str)
        except TypeError:
            text = str(payload)
        if len(text) <= self._max_chars:
            return {"ok": True, "data": payload}
        return {
            "ok": True,
            "truncated": True,
            "data": text[: self._max_chars] + "…",
            "note": "respuesta truncada por límite configurado (PONTI_BACKEND_MAX_RESPONSE_CHARS)",
        }

    async def get_json(
        self,
        path: str,
        *,
        user_id: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not self.is_configured():
            return {"ok": False, "error": "ponti_backend_not_configured"}

        if not path.startswith("/"):
            path = "/" + path
        url = f"{self._base}{path}"
        if params:
            # Filtrar None y armar query
            flat = {k: v for k, v in params.items() if v is not None and v != ""}
            if flat:
                url = f"{url}?{urlencode(flat, doseq=True)}"

        headers: dict[str, str] = {
            "X-API-Key": self._api_key,
            "X-USER-ID": str(user_id or "").strip(),
            "Accept": "application/json",
        }
        if self._auth_extra:
            headers["Authorization"] = self._auth_extra

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(url, headers=headers)
        except httpx.HTTPError as exc:
            return {"ok": False, "error": "http_error", "detail": str(exc)}

        try:
            body = response.json()
        except Exception:  # noqa: BLE001
            body = {"raw": (response.text or "")[:2000]}

        if response.status_code >= 400:
            return {
                "ok": False,
                "status": response.status_code,
                "error": "backend_error",
                "body": body,
            }

        if isinstance(body, dict | list):
            return self._clip(body)
        return self._clip(body)
