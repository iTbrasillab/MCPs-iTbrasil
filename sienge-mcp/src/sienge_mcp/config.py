from __future__ import annotations

import os
from dataclasses import dataclass


DEFAULT_BASE_URL = "https://api.sienge.com.br"
DEFAULT_MEDICOES_ENDPOINT_PATH = "/contracts/measurements"
DEFAULT_AUTH_TEST_ENDPOINT_PATH = "/companies"

# Endpoint temporario ate a confirmacao oficial na documentacao Sienge.
SIENGE_MEDICOES_ENDPOINT_PATH = os.getenv(
    "SIENGE_MEDICOES_ENDPOINT_PATH",
    DEFAULT_MEDICOES_ENDPOINT_PATH,
)
SIENGE_AUTH_TEST_ENDPOINT_PATH = os.getenv(
    "SIENGE_AUTH_TEST_ENDPOINT_PATH",
    DEFAULT_AUTH_TEST_ENDPOINT_PATH,
)


@dataclass(frozen=True)
class SiengeSettings:
    api_key: str | None
    username: str | None
    password: str | None
    subdomain: str | None
    base_url: str
    medicoes_endpoint_path: str
    auth_test_endpoint_path: str
    request_timeout: float

    @classmethod
    def from_env(cls) -> "SiengeSettings":
        subdomain = _read_env("SIENGE_SUBDOMAIN")
        base_url = _resolve_base_url(_read_env("SIENGE_BASE_URL"), subdomain)

        return cls(
            api_key=_read_env("SIENGE_API_KEY"),
            username=_read_env("SIENGE_USERNAME"),
            password=_read_env("SIENGE_PASSWORD"),
            subdomain=subdomain,
            base_url=base_url,
            medicoes_endpoint_path=os.getenv(
                "SIENGE_MEDICOES_ENDPOINT_PATH",
                SIENGE_MEDICOES_ENDPOINT_PATH,
            ),
            auth_test_endpoint_path=os.getenv(
                "SIENGE_AUTH_TEST_ENDPOINT_PATH",
                SIENGE_AUTH_TEST_ENDPOINT_PATH,
            ),
            request_timeout=_read_float_env("SIENGE_REQUEST_TIMEOUT", 30.0),
        )

    def ensure_auth_configured(self) -> None:
        if self.api_key:
            return

        if self.username and self.password:
            return

        raise ValueError(
            "Configure SIENGE_API_KEY ou SIENGE_USERNAME/SIENGE_PASSWORD antes de enviar ao Sienge."
        )


def _read_env(name: str) -> str | None:
    value = os.getenv(name)
    if value is None:
        return None

    value = value.strip()
    return value or None


def _read_float_env(name: str, default: float) -> float:
    value = _read_env(name)
    if value is None:
        return default

    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(f"{name} deve ser numerico.") from exc


def _resolve_base_url(base_url: str | None, subdomain: str | None) -> str:
    if base_url:
        if "{subdomain}" in base_url and subdomain:
            return base_url.format(subdomain=subdomain).rstrip("/")
        return base_url.rstrip("/")

    if subdomain:
        return f"{DEFAULT_BASE_URL}/{subdomain}/public/api/v1"

    return DEFAULT_BASE_URL
