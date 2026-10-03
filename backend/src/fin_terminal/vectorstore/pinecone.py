import httpx

from fin_terminal.schemas import Document
from fin_terminal.vectorstore.base import VectorStoreAdapter


class PineconeVectorAdapter(VectorStoreAdapter):
    """Data-plane adapter; host must point to an existing vector index."""

    def __init__(self, client: httpx.AsyncClient, namespace: str) -> None:
        self.client = client
        self.namespace = namespace

    async def upsert(self, document: Document, vector: list[float]) -> None:
        response = await self.client.post(
            "/vectors/upsert",
            json={
                "namespace": self.namespace,
                "vectors": [
                    {
                        "id": document.content_hash,
                        "values": vector,
                        "metadata": {
                            "content_hash": document.content_hash,
                            "source": document.source,
                            "provider": document.provider,
                            "theme_tags": [tag.value for tag in document.theme_tags],
                        },
                    }
                ],
            },
        )
        response.raise_for_status()

    async def health(self) -> bool:
        try:
            return (await self.client.post("/describe_index_stats", json={})).is_success
        except httpx.HTTPError:
            return False

    async def close(self) -> None:
        await self.client.aclose()
