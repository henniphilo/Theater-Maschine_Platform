from openai import AsyncOpenAI

from app.core.config import settings


class OpenAIProvider:
    def __init__(self) -> None:
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY not configured")
        # Bound hangs so Teil-2 prepare cannot stick forever on a silent API wait.
        self.client = AsyncOpenAI(api_key=settings.openai_api_key, timeout=90.0)

    async def generate(
        self, model: str, messages: list[dict[str, str]], max_tokens: int = 2048
    ) -> str:
        response = await self.client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content or ""
