from abc import ABC, abstractmethod


class BaseLLMProvider(ABC):
    @abstractmethod
    async def complete(self, system: str, user: str, temperature: float = 0.0) -> str:
        """Run a chat completion and return the assistant text."""
        raise NotImplementedError