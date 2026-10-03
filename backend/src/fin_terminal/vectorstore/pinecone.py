from datetime import UTC
from typing import Any

import httpx

from fin_terminal.schemas import Document
from fin_terminal.vectorstore.base import VectorStoreAdapter

MetadataValue = str | int | float | bool | list[str]
MAX_TEXT_CHARS = 600  # metadata snippet (storage/write units); full documents stay in SQLite


def clean_metadata(raw: dict[str, Any]) -> dict[str, MetadataValue]:
    """Pinecone rejects nulls and nested objects: drop them, never invent placeholders."""
    out: dict[str, MetadataValue] = {}
    for key, value in raw.items():
        if value is None or value == "" or value == []:
            continue
        if isinstance(value, bool | int | float | str):
            out[key] = value
        elif isinstance(value, list):
            out[key] = [str(v) for v in value if v is not None and v != ""]
    return out


def document_metadata(document: Document, **extra: Any) -> dict[str, MetadataValue]:
    """Filterable provenance for one record (dates as epoch seconds for range filters)."""
    when = document.published_at or document.observed_at
    text = document.text or ""
    return clean_metadata(
        {
            "content_hash": document.content_hash,
            "kind": document.kind,
            "source": document.source,
            "provider": document.provider,
            "source_url": document.source_url,
            "title": getattr(document, "title", None),
            "text": text[:MAX_TEXT_CHARS],
            "published_ts": int(when.astimezone(UTC).timestamp()) if when else None,
            "year": when.year if when else None,
            "theme_tags": [tag.value for tag in document.theme_tags],
            "data_quality": document.data_quality,
            **extra,
        }
    )


class PineconeVectorAdapter(VectorStoreAdapter):
    """Data-plane adapter; host must point to an existing vector index."""

    def __init__(self, client: httpx.AsyncClient, namespace: str) -> None:
        self.client = client
        self.namespace = namespace

    async def upsert(self, document: Document, vector: list[float]) -> None:
        await self.upsert_many([(document.content_hash, vector, document_metadata(document))])

    async def upsert_many(
        self,
        items: list[tuple[str, list[float], dict[str, MetadataValue]]],
        namespace: str | None = None,
    ) -> None:
        """One request per call; keep batches ≤ ~200 records to stay under the 2 MB limit."""
        if not items:
            return
        response = await self.client.post(
            "/vectors/upsert",
            json={
                "namespace": namespace or self.namespace,
                "vectors": [
                    {"id": item_id, "values": vector, "metadata": metadata}
                    for item_id, vector, metadata in items
                ],
            },
        )
        response.raise_for_status()

    async def query(
        self,
        vector: list[float],
        *,
        top_k: int = 10,
        filter: dict[str, Any] | None = None,
        namespace: str | None = None,
    ) -> list[dict[str, Any]]:
        body: dict[str, Any] = {
            "namespace": namespace or self.namespace,
            "vector": vector,
            "topK": top_k,
            "includeMetadata": True,
        }
        if filter:
            body["filter"] = filter
        response = await self.client.post("/query", json=body)
        response.raise_for_status()
        return list(response.json().get("matches", []))

    async def delete_namespace(self, namespace: str) -> None:
        response = await self.client.post(
            "/vectors/delete", json={"deleteAll": True, "namespace": namespace}
        )
        if response.status_code != 404:  # 404: namespace already empty
            response.raise_for_status()

    async def delete_ids(self, ids: list[str], namespace: str) -> None:
        for start in range(0, len(ids), 1000):  # API limit: 1000 ids per call
            response = await self.client.post(
                "/vectors/delete", json={"ids": ids[start : start + 1000], "namespace": namespace}
            )
            response.raise_for_status()

    async def stats(self) -> dict[str, Any]:
        response = await self.client.post("/describe_index_stats", json={})
        response.raise_for_status()
        return dict(response.json())

    async def health(self) -> bool:
        try:
            return (await self.client.post("/describe_index_stats", json={})).is_success
        except httpx.HTTPError:
            return False

    async def close(self) -> None:
        await self.client.aclose()
