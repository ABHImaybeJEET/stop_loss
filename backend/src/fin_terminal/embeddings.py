"""Load real embedding wrappers lazily; empty stub runs download nothing."""

from functools import cached_property

from langchain_core.embeddings import Embeddings

from fin_terminal.config import Settings, secret_value


class LazyEmbeddings:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @cached_property
    def model(self) -> Embeddings:
        if self.settings.embedding_backend == "openai":
            from langchain_openai import OpenAIEmbeddings

            return OpenAIEmbeddings(
                model=self.settings.openai_embedding_model,
                api_key=secret_value(self.settings.openai_api_key),
            )
        from langchain_huggingface import HuggingFaceEmbeddings

        return HuggingFaceEmbeddings(model_name=self.settings.embedding_model_name)

    async def embed(self, text: str) -> list[float]:
        # Model construction can load weights; keep it off the event loop.
        import asyncio

        model = await asyncio.to_thread(lambda: self.model)
        return (await model.aembed_documents([text]))[0]
