"""Async Groq chat adapter without native tokenizer dependencies."""

from typing import Any

import httpx
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import RunnableLambda
from pydantic import BaseModel, Field, SecretStr
from tenacity import AsyncRetrying, retry_if_exception, stop_after_attempt, wait_random_exponential


class GroqChatModel(BaseChatModel):
    api_key: SecretStr = Field(exclude=True, repr=False)
    model: str = "openai/gpt-oss-20b"
    timeout_seconds: float = 60

    @property
    def _llm_type(self) -> str:
        return "groq"

    def _generate(self, messages: list[BaseMessage], **kwargs: Any) -> ChatResult:
        raise NotImplementedError("GroqChatModel uses async invocation")

    async def _request(self, messages: list[BaseMessage], schema: type[BaseModel] | None = None):
        body: dict[str, Any] = {
            "model": self.model,
            "temperature": 0.2,
            "messages": [
                {
                    "role": {"human": "user", "ai": "assistant"}.get(m.type, m.type),
                    "content": m.content,
                }
                for m in messages
            ],
        }
        if schema:
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": schema.__name__,
                    "schema": schema.model_json_schema(),
                    "strict": False,
                },
            }

        def transient(exc: BaseException) -> bool:
            return isinstance(exc, httpx.TransportError) or (
                isinstance(exc, httpx.HTTPStatusError)
                and (exc.response.status_code == 429 or exc.response.status_code >= 500)
            )

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(3),
                wait=wait_random_exponential(max=4),
                retry=retry_if_exception(transient),
                reraise=True,
            ):
                with attempt:
                    response = await client.post(
                        "https://api.groq.com/openai/v1/chat/completions",
                        headers={"Authorization": f"Bearer {self.api_key.get_secret_value()}"},
                        json=body,
                    )
                    response.raise_for_status()
                    return response.json()["choices"][0]["message"]["content"]
        raise RuntimeError("Groq request did not complete")

    async def _agenerate(self, messages: list[BaseMessage], **kwargs: Any) -> ChatResult:
        return ChatResult(
            generations=[ChatGeneration(message=AIMessage(content=await self._request(messages)))]
        )

    def with_structured_output(self, schema, **kwargs):
        async def invoke(messages):
            return schema.model_validate_json(await self._request(messages, schema))

        return RunnableLambda(invoke, name=self.name or "groq-structured-output")
