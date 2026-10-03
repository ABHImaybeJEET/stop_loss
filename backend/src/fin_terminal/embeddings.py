"""Load real embedding wrappers lazily; empty stub runs download nothing."""

import hashlib
import logging
import math
from threading import Lock

from langchain_core.embeddings import Embeddings

from fin_terminal.config import Settings, secret_value

logger = logging.getLogger("fin_terminal")


class LightweightFeatureEmbeddings(Embeddings):
    """Deterministic, sub-millisecond unit-norm feature embedding for offline/fallback execution."""

    def __init__(self, dimensions: int = 384) -> None:
        self.dimensions = dimensions

    def _embed_text(self, text: str) -> list[float]:
        vec = [0.0] * self.dimensions
        tokens = text.lower().split()
        if not tokens:
            tokens = [text]
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            idx = int.from_bytes(digest[:4], "big") % self.dimensions
            val = (int.from_bytes(digest[4:8], "big") / 0xFFFFFFFF) * 2.0 - 1.0
            vec[idx] += val
        norm = math.sqrt(sum(x * x for x in vec))
        if norm > 0:
            vec = [x / norm for x in vec]
        return vec

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_text(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed_text(text)


class LazyEmbeddings:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._model: Embeddings | None = None
        self._model_lock = Lock()

    @property
    def model(self) -> Embeddings:
        with self._model_lock:
            if self._model is None:
                self._model = self._load_model()
            return self._model

    def _load_model(self) -> Embeddings:
        if self.settings.embedding_backend == "openai":
            from langchain_openai import OpenAIEmbeddings

            return OpenAIEmbeddings(
                model=self.settings.openai_embedding_model,
                api_key=secret_value(self.settings.openai_api_key),
            )
        try:
            from langchain_huggingface import HuggingFaceEmbeddings

            return HuggingFaceEmbeddings(model_name=self.settings.embedding_model_name)
        except ImportError:
            logger.info("Using lightweight 384-d feature embeddings (HuggingFace not installed)")
            return LightweightFeatureEmbeddings(dimensions=384)

    async def embed(self, text: str) -> list[float]:
        import asyncio

        model = await asyncio.to_thread(lambda: self.model)
        return (await model.aembed_documents([text]))[0]
