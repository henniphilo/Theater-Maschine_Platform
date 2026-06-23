from app.schemas.discussion import DramaturgSpeaker

CLAUDE_LABEL = "Claude"
CHATGPT_LABEL = "ChatGPT"


def dramaturg_display_name(speaker: DramaturgSpeaker | str) -> str:
    if speaker == "anthropic":
        return CLAUDE_LABEL
    if speaker == "openai":
        return CHATGPT_LABEL
    return str(speaker)


def dramaturg_speaker_from_label(label: str) -> DramaturgSpeaker:
    normalized = label.strip().lower()
    if normalized in ("claude", "anthropic"):
        return "anthropic"
    return "openai"
