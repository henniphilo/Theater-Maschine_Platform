from tenacity import retry, stop_after_attempt, wait_exponential

from app.services.providers.anthropic_provider import AnthropicProvider
from app.services.providers.base import ChatProvider
from app.services.providers.openai_provider import OpenAIProvider


class AIService:
    def __init__(self) -> None:
        self.providers: dict[str, ChatProvider] = {}
        self._init_provider("openai")
        self._init_provider("anthropic")

    def _init_provider(self, provider: str) -> None:
        try:
            if provider == "openai":
                self.providers[provider] = OpenAIProvider()
            elif provider == "anthropic":
                self.providers[provider] = AnthropicProvider()
        except RuntimeError:
            # Keep app booting even if one provider is not configured yet.
            return

    @retry(wait=wait_exponential(multiplier=1, min=1, max=8), stop=stop_after_attempt(3))
    async def generate(
        self, provider: str, model: str, messages: list[dict[str, str]], max_tokens: int = 2048
    ) -> str:
        adapter = self.providers.get(provider)
        if adapter is None:
            raise ValueError(f"Unsupported provider: {provider}")
        return await adapter.generate(model, messages, max_tokens=max_tokens)
