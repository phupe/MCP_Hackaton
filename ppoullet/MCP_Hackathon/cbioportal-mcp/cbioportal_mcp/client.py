"""Thin async HTTP client for the cBioPortal REST API.

API reference: https://docs.cbioportal.org/web-api-and-clients/
Live Swagger UI: https://www.cbioportal.org/api/swagger-ui/index.html
"""

from __future__ import annotations

import os
from typing import Any

import httpx

DEFAULT_BASE_URL = "https://www.cbioportal.org/api"


class CBioPortalError(RuntimeError):
    """Raised when the cBioPortal API returns an error response."""

    def __init__(self, status_code: int, method: str, url: str, body: str):
        self.status_code = status_code
        self.method = method
        self.url = url
        self.body = body
        super().__init__(f"{method} {url} -> HTTP {status_code}: {body[:2000]}")


class CBioPortalClient:
    """Thin wrapper around the cBioPortal REST API.

    The base URL and an optional bearer token are read from environment
    variables so the same server can point at the public instance
    (https://www.cbioportal.org/api) or a private/institutional one.
    """

    def __init__(self, base_url: str | None = None, token: str | None = None, timeout: float = 60.0):
        self.base_url = (base_url or os.environ.get("CBIOPORTAL_API_URL") or DEFAULT_BASE_URL).rstrip("/")
        self.token = token or os.environ.get("CBIOPORTAL_API_TOKEN")
        headers = {"Accept": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        self._client = httpx.AsyncClient(base_url=self.base_url, headers=headers, timeout=timeout)

    async def aclose(self) -> None:
        await self._client.aclose()

    @staticmethod
    def _clean_params(params: dict[str, Any] | None) -> dict[str, Any]:
        if not params:
            return {}
        return {k: v for k, v in params.items() if v is not None}

    async def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        resp = await self._client.get(path, params=self._clean_params(params))
        return self._handle(resp)

    async def post(
        self,
        path: str,
        json_body: Any = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        resp = await self._client.post(path, json=json_body, params=self._clean_params(params))
        return self._handle(resp)

    @staticmethod
    def _handle(resp: httpx.Response) -> Any:
        if resp.status_code >= 400:
            raise CBioPortalError(resp.status_code, resp.request.method, str(resp.request.url), resp.text)
        if not resp.content:
            return None
        return resp.json()
