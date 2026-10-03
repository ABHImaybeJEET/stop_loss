"""Semantic retrieval over the indexed history (historical analogs, past news, profiles)."""

from dataclasses import dataclass
from typing import Any

from fin_terminal.embeddings import LazyEmbeddings
from fin_terminal.vectorstore.pinecone import PineconeVectorAdapter


@dataclass(frozen=True)
class Hit:
    id: str
    score: float
    metadata: dict[str, Any]

    @property
    def text(self) -> str:
        return str(self.metadata.get("text") or self.metadata.get("title") or "")


def build_filter(
    *,
    doc_types: list[str] | None = None,
    year_from: int | None = None,
    year_to: int | None = None,
    tickers: list[str] | None = None,
    themes: list[str] | None = None,
) -> dict[str, Any] | None:
    clauses: list[dict[str, Any]] = []
    if doc_types:
        clauses.append({"doc_type": {"$in": doc_types}})
    if year_from is not None:
        clauses.append({"year": {"$gte": year_from}})
    if year_to is not None:
        clauses.append({"year": {"$lte": year_to}})
    if tickers:
        clauses.append({"tickers": {"$in": tickers}})
    if themes:
        clauses.append({"theme_tags": {"$in": themes}})
    if not clauses:
        return None
    return clauses[0] if len(clauses) == 1 else {"$and": clauses}


class HistoricalRetriever:
    def __init__(self, embedder: LazyEmbeddings, adapter: PineconeVectorAdapter, namespace: str):
        self.embedder = embedder
        self.adapter = adapter
        self.namespace = namespace

    async def search(self, query: str, *, top_k: int = 8, **filters: Any) -> list[Hit]:
        vector = await self.embedder.embed_query(query)
        matches = await self.adapter.query(
            vector, top_k=top_k, filter=build_filter(**filters), namespace=self.namespace
        )
        return [
            Hit(
                id=str(m.get("id")),
                score=float(m.get("score", 0.0)),
                metadata=m.get("metadata") or {},
            )
            for m in matches
        ]
