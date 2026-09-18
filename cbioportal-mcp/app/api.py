"""HTTP transport for the public cBioPortal REST API."""

import os
from typing import Any

import httpx
from mcp.server.mcpserver.exceptions import ToolError

API_BASE_URL = os.environ.get("CBIOPORTAL_API_BASE_URL", "https://www.cbioportal.org/api").rstrip("/")


async def request(
    method: str, path: str, *, params: dict[str, Any] | None = None, json: Any = None
) -> Any:
    """Call the public API and convert recoverable failures to ToolErrors."""
    url = f"{API_BASE_URL}{path}"
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
            response = await client.request(method, url, params=params, json=json)
    except httpx.TimeoutException as exc:
        raise ToolError("cBioPortal did not respond within 30 seconds. Please retry.") from exc
    except httpx.RequestError as exc:
        raise ToolError(f"Could not reach cBioPortal at {API_BASE_URL}. Please retry later.") from exc

    if response.status_code == 404:
        raise ToolError(
            "cBioPortal did not find that resource. Check the study, profile, sample, or gene "
            "identifier and discover valid IDs with the list tools."
        )
    if response.status_code in (401, 403):
        raise ToolError(
            "This cBioPortal resource is not public. Choose a public study or configure an "
            "authorized API endpoint with CBIOPORTAL_API_BASE_URL."
        )
    if response.status_code == 429:
        raise ToolError("cBioPortal rate-limited this request. Wait briefly, then retry.")
    if response.is_error:
        raise ToolError(
            f"cBioPortal returned HTTP {response.status_code}. Check the supplied identifiers "
            "and retry."
        )
    try:
        return response.json()
    except ValueError as exc:
        raise ToolError("cBioPortal returned an unexpected non-JSON response. Please retry.") from exc
