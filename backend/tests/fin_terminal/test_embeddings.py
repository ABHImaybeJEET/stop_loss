import asyncio
import time
from unittest.mock import Mock

from fin_terminal.embeddings import LazyEmbeddings


def test_concurrent_first_records_load_one_model(settings, monkeypatch):
    embedder = LazyEmbeddings(settings)

    class Model:
        async def aembed_documents(self, texts):
            return [[0.1, 0.2] for _ in texts]

    def load():
        time.sleep(0.03)
        return Model()

    loader = Mock(side_effect=load)
    monkeypatch.setattr(embedder, "_load_model", loader)

    async def exercise():
        vectors = await asyncio.gather(*(embedder.embed("fixture") for _ in range(8)))
        assert vectors == [[0.1, 0.2]] * 8

    asyncio.run(exercise())
    loader.assert_called_once()
