from groq import AsyncGroq

from app.ai.providers.base import BaseLLMProvider


class GroqAdapter(BaseLLMProvider):
    """Groq chat-completion provider backed by the Groq SDK.

    Supports a pool of API keys (ideally from separate accounts) so a 429
    rate limit on one key can fail over to the next via :meth:`rotate`.
    """

    def __init__(self, api_keys: list[str], model: str):
        if not api_keys or not any(api_keys):
            raise ValueError("GROQ_API_KEY is not configured")
        self._model = model
        self._clients = [AsyncGroq(api_key=k) for k in api_keys]
        self._index = 0

    def _client(self) -> AsyncGroq:
        return self._clients[self._index % len(self._clients)]

    def rotate(self) -> None:
        """Advance to the next key in the pool (on a rate limit)."""
        self._index = (self._index + 1) % len(self._clients)

    async def complete(
        self, system: str, user: str, temperature: float = 0.0, max_tokens: int | None = None
    ) -> str:
        response = await self._client().chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=temperature,
            **({"max_tokens": max_tokens} if max_tokens else {}),
        )
        if not response.choices:
            raise RuntimeError("Groq returned no completions")
        return response.choices[0].message.content or ""
