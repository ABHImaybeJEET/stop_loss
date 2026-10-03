import httpx

from fin_terminal.config import Settings, secret_value
from fin_terminal.vectorstore.base import VectorStoreAdapter
from fin_terminal.vectorstore.pinecone import PineconeVectorAdapter
from fin_terminal.vectorstore.weaviate import WeaviateVectorAdapter


def create_vectorstore(settings: Settings) -> VectorStoreAdapter:
    if settings.vector_backend == "weaviate":
        key = secret_value(settings.weaviate_api_key)
        return WeaviateVectorAdapter(
            httpx.AsyncClient(
                base_url=settings.weaviate_url,
                headers={"Authorization": f"Bearer {key}"} if key else {},
                timeout=settings.http_timeout_seconds,
            ),
            settings.weaviate_collection,
        )
    key = secret_value(settings.pinecone_api_key)
    if not key or not settings.pinecone_host.startswith("https://"):
        raise ValueError("Pinecone requires PINECONE_API_KEY and an https PINECONE_HOST")
    return PineconeVectorAdapter(
        httpx.AsyncClient(
            base_url=settings.pinecone_host,
            headers={"Api-Key": key, "X-Pinecone-API-Version": "2025-10"},
            timeout=settings.http_timeout_seconds,
        ),
        settings.pinecone_namespace,
    )
