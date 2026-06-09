from anthropic import AsyncAnthropic

from app.core.config import settings


class AnthropicProvider:
    def __init__(self) -> None:
        if not settings.anthropic_api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not configured")
        self.client = AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def generate(
        self, model: str, messages: list[dict[str, str]], max_tokens: int = 2048
    ) -> str:
        system = next((m["content"] for m in messages if m["role"] == "system"), "")
        chat_messages = [m for m in messages if m["role"] != "system"]
        response = await self.client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=chat_messages,
        )
        return response.content[0].text
