import httpx

from fin_terminal.config import Settings, secret_value
from fin_terminal.vectorstore.base import VectorStoreAdapter
from fin_terminal.vectorstore.pinecone import PineconeVectorAdapter
from fin_terminal.vectorstore.pinecone_control import resolve_host
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
    if not key:
        raise ValueError("Pinecone requires PINECONE_API_KEY and an https PINECONE_HOST")
    # An explicit PINECONE_HOST wins; otherwise look up the host of PINECONE_INDEX_NAME.
    host = settings.pinecone_host or resolve_host(settings)
    if not host.startswith("https://"):
        raise ValueError("Pinecone requires PINECONE_API_KEY and an https PINECONE_HOST")
    return PineconeVectorAdapter(
        httpx.AsyncClient(
            base_url=host,
            headers={"Api-Key": key, "X-Pinecone-API-Version": "2025-10"},
            timeout=settings.http_timeout_seconds,
        ),
        settings.pinecone_namespace,
    )
