from app.services.dramaturg_labels import CHATGPT_LABEL, CLAUDE_LABEL, dramaturg_display_name


def test_dramaturg_labels() -> None:
    assert dramaturg_display_name("anthropic") == CLAUDE_LABEL
    assert dramaturg_display_name("openai") == CHATGPT_LABEL
    assert CLAUDE_LABEL == "Claude"
    assert CHATGPT_LABEL == "ChatGPT"
