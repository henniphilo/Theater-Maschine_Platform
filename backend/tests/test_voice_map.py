from app.services.tts.performance_voices import performance_speaker_for_sentence
from app.services.tts.voice_map import voice_for_speaker


def test_dramaturg_and_performance_voices_differ_on_edge() -> None:
    dramaturg_openai = voice_for_speaker("openai", provider="edge")
    dramaturg_anthropic = voice_for_speaker("anthropic", provider="edge")
    performance_a = voice_for_speaker("AI_A", provider="edge", profile="performance")
    performance_b = voice_for_speaker("AI_B", provider="edge", profile="performance")
    narrator = voice_for_speaker("narrator", provider="edge", profile="performance")

    assert dramaturg_openai != performance_a
    assert dramaturg_anthropic != performance_b
    assert performance_a != performance_b
    assert narrator not in {dramaturg_openai, dramaturg_anthropic}


def test_inszenierung_profile_uses_separate_voices() -> None:
    performance_a = voice_for_speaker("AI_A", provider="edge", profile="performance")
    inszenierung_a = voice_for_speaker("AI_A", provider="edge", profile="inszenierung")
    assert performance_a != inszenierung_a


def test_performance_speaker_rotates_across_sentences() -> None:
    speakers = [
        performance_speaker_for_sentence("AI_A", i, beat_order=0) for i in range(6)
    ]
    assert speakers == ["AI_A", "AI_B", "narrator", "AI_A", "AI_B", "narrator"]


def test_performance_speaker_uses_custom_pool() -> None:
    speakers = [
        performance_speaker_for_sentence("AI_A", i, beat_order=0, pool=["AI_A", "AI_B"])
        for i in range(4)
    ]
    assert speakers == ["AI_A", "AI_B", "AI_A", "AI_B"]
