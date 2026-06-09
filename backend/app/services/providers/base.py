from typing import Protocol


class ChatProvider(Protocol):
    async def generate(
        self, model: str, messages: list[dict[str, str]], max_tokens: int = 2048
    ) -> str:
        ...
