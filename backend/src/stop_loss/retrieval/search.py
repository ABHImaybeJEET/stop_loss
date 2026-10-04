"""Semantic retrieval over the indexed history (historical analogs, past news, profiles)
and the live namespace: one query per namespace, merged by score, each hit tagged."""

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

from fin_terminal.embeddings import LazyEmbeddings
from fin_terminal.vectorstore.pinecone import PineconeVectorAdapter

logger = logging.getLogger("stop_loss.retrieval")


@dataclass(frozen=True)
class Hit:
    id: str
    score: float
    metadata: dict[str, Any]
    namespace: str = ""

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
    regions: list[str] | None = None,
    min_category: int | None = None,
) -> dict[str, Any] | None:
    """Structured narrowing first (dense ranking alone conflates templated event texts)."""
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
    if regions:
        clauses.append({"region": {"$in": regions}})
    if min_category is not None:
        clauses.append({"intensity_category": {"$gte": min_category}})
    if not clauses:
        return None
    return clauses[0] if len(clauses) == 1 else {"$and": clauses}


class HistoricalRetriever:
    def __init__(
        self,
        embedder: LazyEmbeddings,
        adapter: PineconeVectorAdapter,
        namespace: str,
        *extra_namespaces: str,
    ):
        self.embedder = embedder
        self.adapter = adapter
        self.namespace = namespace
        self.namespaces = tuple(dict.fromkeys((namespace, *extra_namespaces)))

    async def search(self, query: str, *, top_k: int = 8, **filters: Any) -> list[Hit]:
        """Top-k across all namespaces by score. Cosine scores from one index and one model
        are directly comparable, so a plain merge is sound. A failing extra namespace
        degrades to the others; if every namespace fails, the first error is raised."""
        vector = await self.embedder.embed_query(query)
        flt = build_filter(**filters)
        results = await asyncio.gather(
            *(
                self.adapter.query(vector, top_k=top_k, filter=flt, namespace=ns)
                for ns in self.namespaces
            ),
            return_exceptions=True,
        )
        errors = [r for r in results if isinstance(r, BaseException)]
        if len(errors) == len(results):
            raise errors[0]
        hits: list[Hit] = []
        for ns, matches in zip(self.namespaces, results, strict=True):
            if isinstance(matches, BaseException):
                logger.warning("namespace %s query failed: %s", ns, type(matches).__name__)
                continue
            hits += [
                Hit(
                    id=str(m.get("id")),
                    score=float(m.get("score", 0.0)),
                    metadata=m.get("metadata") or {},
                    namespace=ns,
                )
                for m in matches
            ]
        return sorted(hits, key=lambda h: h.score, reverse=True)[:top_k]
