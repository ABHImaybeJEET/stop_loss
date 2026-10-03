from uuid import NAMESPACE_URL, uuid5

import httpx

from fin_terminal.schemas import Document
from fin_terminal.vectorstore.base import VectorStoreAdapter


class WeaviateVectorAdapter(VectorStoreAdapter):
    """REST adapter for a self-provided-vector collection (vectorizer=none)."""

    def __init__(self, client: httpx.AsyncClient, collection: str) -> None:
        self.client = client
        self.collection = collection
        self._ready = False

    async def _ensure_collection(self) -> None:
        if self._ready:
            return
        response = await self.client.get(f"/v1/schema/{self.collection}")
        if response.status_code == 404:
            response = await self.client.post(
                "/v1/schema",
                json={
                    "class": self.collection,
                    "vectorizer": "none",
                    "properties": [
                        {"name": "content_hash", "dataType": ["text"]},
                        {"name": "source", "dataType": ["text"]},
                        {"name": "provider", "dataType": ["text"]},
                        {"name": "theme_tags", "dataType": ["text[]"]},
                    ],
                },
            )
        response.raise_for_status()
        self._ready = True

    async def upsert(self, document: Document, vector: list[float]) -> None:
        await self._ensure_collection()
        object_id = str(uuid5(NAMESPACE_URL, document.content_hash))
        payload = {
            "class": self.collection,
            "id": object_id,
            "vector": vector,
            "properties": {
                "content_hash": document.content_hash,
                "source": document.source,
                "provider": document.provider,
                "theme_tags": [tag.value for tag in document.theme_tags],
            },
        }
        response = await self.client.put(f"/v1/objects/{self.collection}/{object_id}", json=payload)
        if response.status_code == 404:
            response = await self.client.post("/v1/objects", json=payload)
        response.raise_for_status()

    async def health(self) -> bool:
        try:
            return (await self.client.get("/v1/.well-known/ready")).is_success
        except httpx.HTTPError:
            return False

    async def close(self) -> None:
        await self.client.aclose()
