"""Pinecone control plane: create/describe the serverless index and resolve its data host."""

import time
from typing import Any

import httpx

from fin_terminal.config import Settings, secret_value

CONTROL_PLANE = "https://api.pinecone.io"
API_VERSION = "2025-10"


def _headers(settings: Settings) -> dict[str, str]:
    key = secret_value(settings.pinecone_api_key)
    if not key:
        raise ValueError("Pinecone requires PINECONE_API_KEY")
    return {"Api-Key": key, "X-Pinecone-API-Version": API_VERSION}


def index_name(settings: Settings) -> str:
    return getattr(settings, "pinecone_index_name", None) or "stop-loss-records"


def describe_index(settings: Settings, client: httpx.Client | None = None) -> dict[str, Any] | None:
    http = client or httpx.Client(timeout=settings.http_timeout_seconds)
    try:
        response = http.get(
            f"{CONTROL_PLANE}/indexes/{index_name(settings)}", headers=_headers(settings)
        )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return dict(response.json())
    finally:
        if client is None:
            http.close()


def ensure_index(
    settings: Settings, *, wait_seconds: float = 120, client: httpx.Client | None = None
) -> dict[str, Any]:
    """Create the cosine serverless index if missing; verify the dimension if present."""
    http = client or httpx.Client(timeout=settings.http_timeout_seconds)
    try:
        existing = describe_index(settings, http)
        if existing is None:
            response = http.post(
                f"{CONTROL_PLANE}/indexes",
                headers=_headers(settings),
                json={
                    "name": index_name(settings),
                    "dimension": settings.embedding_dimensions,
                    "metric": "cosine",
                    "spec": {
                        "serverless": {
                            "cloud": settings.pinecone_cloud,
                            "region": settings.pinecone_region,
                        }
                    },
                    "deletion_protection": "disabled",
                },
            )
            response.raise_for_status()
            existing = dict(response.json())
        elif existing.get("dimension") != settings.embedding_dimensions:
            raise ValueError(
                f"Index '{index_name(settings)}' has dimension {existing.get('dimension')} but "
                f"EMBEDDING_DIMENSIONS={settings.embedding_dimensions}; use another index name"
            )
        deadline = time.monotonic() + wait_seconds
        while not (existing.get("status") or {}).get("ready"):
            if time.monotonic() > deadline:
                raise TimeoutError("Pinecone index did not become ready in time")
            time.sleep(3)
            existing = describe_index(settings, http) or existing
        return existing
    finally:
        if client is None:
            http.close()


def resolve_host(settings: Settings) -> str:
    """PINECONE_HOST if set, otherwise the host of PINECONE_INDEX_NAME."""
    if settings.pinecone_host:
        return settings.pinecone_host
    described = describe_index(settings)
    if not described or not described.get("host"):
        raise ValueError(
            f"Pinecone index '{index_name(settings)}' not found; run `stop-loss-vectors init`"
        )
    host = str(described["host"])
    return host if host.startswith("https://") else f"https://{host}"
