from openai import AsyncOpenAI

from app.core.config import settings


class OpenAIProvider:
    def __init__(self) -> None:
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY not configured")
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)

    async def generate(
        self, model: str, messages: list[dict[str, str]], max_tokens: int = 2048
    ) -> str:
        response = await self.client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content or ""
