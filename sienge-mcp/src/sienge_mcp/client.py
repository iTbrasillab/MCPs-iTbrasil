from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

import httpx

from .config import SiengeSettings


ErrorType = Literal["timeout", "request_error"]


@dataclass(frozen=True)
class SiengeApiResponse:
    status_code: int | None
    body: Any | None = None
    text: str | None = None
    error_type: ErrorType | None = None
    message: str | None = None


class SiengeClient:
    def __init__(
        self,
        settings: SiengeSettings | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.settings = settings or SiengeSettings.from_env()
        self.settings.ensure_auth_configured()
        self._external_client = http_client is not None
        self._client = http_client or httpx.AsyncClient(
            timeout=self.settings.request_timeout,
            headers=self._headers(),
            auth=self._auth(),
        )

    async def post_json(self, path: str, payload: dict[str, Any]) -> SiengeApiResponse:
        return await self._request_json("POST", path, payload)

    async def get_json(self, path: str) -> SiengeApiResponse:
        return await self._request_json("GET", path)

    async def _request_json(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> SiengeApiResponse:
        try:
            response = await self._client.request(method, self._url(path), json=payload)
        except httpx.TimeoutException:
            return SiengeApiResponse(
                status_code=None,
                error_type="timeout",
                message="tempo limite excedido",
            )
        except httpx.RequestError as exc:
            return SiengeApiResponse(
                status_code=None,
                error_type="request_error",
                message=str(exc),
            )

        return SiengeApiResponse(
            status_code=response.status_code,
            body=_response_body(response),
            text=response.text,
        )

    async def aclose(self) -> None:
        if not self._external_client:
            await self._client.aclose()

    def _url(self, path: str) -> str:
        return f"{self.settings.base_url.rstrip('/')}/{path.lstrip('/')}"

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "sienge-mcp/0.1.0",
        }

        if self.settings.api_key:
            headers["Authorization"] = f"Bearer {self.settings.api_key}"

        return headers

    def _auth(self) -> httpx.Auth | None:
        if self.settings.api_key:
            return None

        if self.settings.username and self.settings.password:
            return httpx.BasicAuth(self.settings.username, self.settings.password)

        return None


def _response_body(response: httpx.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        return response.text
