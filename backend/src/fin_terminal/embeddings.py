"""Load real embedding wrappers lazily; empty stub runs download nothing."""

import asyncio
import hashlib
import logging
import math
from threading import Lock

from langchain_core.embeddings import Embeddings

from fin_terminal.config import Settings, secret_value

logger = logging.getLogger("fin_terminal")


class LightweightFeatureEmbeddings(Embeddings):
    """Deterministic, sub-millisecond unit-norm feature embedding for offline/fallback execution.

    Hashes tokens into buckets: useful for tests and wiring, NOT for semantic retrieval.
    """

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


class TransformerEmbeddings(Embeddings):
    """Sentence embeddings straight from `transformers` (BGE: CLS pooling + L2 norm).

    Equivalent to sentence-transformers for BGE models, without its scikit-learn
    dependency (blocked by Windows Application Control on the dev machine).
    """

    def __init__(
        self,
        model_name: str,
        *,
        device: str,
        batch_size: int,
        query_instruction: str = "",
        max_length: int = 512,
    ) -> None:
        import torch
        from transformers import AutoModel, AutoTokenizer

        self._torch = torch
        self.device = device
        self.batch_size = batch_size
        self.query_instruction = query_instruction
        self.max_length = max_length
        self.cls_pooling = "bge" in model_name.lower()
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        dtype = torch.float16 if device == "cuda" else torch.float32
        self.model = AutoModel.from_pretrained(model_name, dtype=dtype).to(device).eval()
        self._lock = Lock()  # one GPU forward pass at a time

    def _encode(self, texts: list[str]) -> list[list[float]]:
        torch = self._torch
        vectors: list[list[float]] = []
        for start in range(0, len(texts), self.batch_size):
            batch = self.tokenizer(
                texts[start : start + self.batch_size],
                padding=True,
                truncation=True,
                max_length=self.max_length,
                return_tensors="pt",
            ).to(self.device)
            with self._lock, torch.inference_mode():
                hidden = self.model(**batch).last_hidden_state
                if self.cls_pooling:
                    pooled = hidden[:, 0]
                else:
                    mask = batch["attention_mask"].unsqueeze(-1).to(hidden.dtype)
                    pooled = (hidden * mask).sum(1) / mask.sum(1).clamp(min=1e-9)
                pooled = torch.nn.functional.normalize(pooled.float(), dim=-1)
            vectors.extend(pooled.cpu().tolist())
        return vectors

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._encode(texts)

    def embed_query(self, text: str) -> list[float]:
        return self._encode([f"{self.query_instruction}{text}"])[0]


def resolve_device(requested: str) -> str:
    if requested != "auto":
        return requested
    try:
        import torch

        return "cuda" if torch.cuda.is_available() else "cpu"
    except ImportError:
        return "cpu"


class LazyEmbeddings:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._model: Embeddings | None = None
        self._model_lock = Lock()
        self.semantic = True

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
            import torch  # noqa: F401
            import transformers  # noqa: F401
        except ImportError:
            self.semantic = False
            logger.warning(
                "Local embedding model unavailable (install the 'local-embeddings' extra); "
                "using NON-SEMANTIC hash features. Do not index these vectors for retrieval."
            )
            return LightweightFeatureEmbeddings(dimensions=self.settings.embedding_dimensions)
        device = resolve_device(self.settings.embedding_device)
        logger.info("Loading %s on %s", self.settings.embedding_model_name, device)
        return TransformerEmbeddings(
            self.settings.embedding_model_name,
            device=device,
            batch_size=self.settings.embedding_batch_size,
            query_instruction=self.settings.embedding_query_instruction,
        )

    async def embed(self, text: str) -> list[float]:
        model = await asyncio.to_thread(lambda: self.model)
        return (await model.aembed_documents([text]))[0]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Document vectors for many texts in one GPU pass (bulk backfills)."""
        model = await asyncio.to_thread(lambda: self.model)
        return await asyncio.to_thread(model.embed_documents, texts)

    async def embed_query(self, text: str) -> list[float]:
        """Query vector (BGE query instruction applied)."""
        model = await asyncio.to_thread(lambda: self.model)
        return await asyncio.to_thread(model.embed_query, text)
