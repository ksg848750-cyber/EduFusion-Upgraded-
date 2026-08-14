from groq import AsyncGroq

from app.ai.providers.base import BaseLLMProvider


class GroqAdapter(BaseLLMProvider):
    """Groq chat-completion provider backed by the Groq SDK.

    Used for concept/relationship extraction (complex: llama-3.3-70b) and
    simple/fast tasks (llama-3.1-8b).
    """

    def __init__(self, api_key: str, model: str):
        if not api_key:
            raise ValueError("GROQ_API_KEY is not configured")
        self._model = model
        self._client = AsyncGroq(api_key=api_key)

    async def complete(self, system: str, user: str, temperature: float = 0.0) -> str:
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=temperature,
        )
        if not response.choices:
            raise RuntimeError("Groq returned no completions")
        return response.choices[0].message.content or ""