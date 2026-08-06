from app.schemas.director import DramaturgyAnalysisEntry
from app.services.dramaturgy_analysis_service import build_analysis_summary


def test_build_analysis_summary_counts_silence_and_blocks() -> None:
    entries = [
        DramaturgyAnalysisEntry(
            decision_id="1",
            created_at="2026-01-01T00:00:00Z",
            decision="execute",
            dramaturgical_function="support",
            executed=True,
        ),
        DramaturgyAnalysisEntry(
            decision_id="2",
            created_at="2026-01-01T00:01:00Z",
            decision="none",
            dramaturgical_function="space",
            executed=True,
        ),
        DramaturgyAnalysisEntry(
            decision_id="3",
            created_at="2026-01-01T00:02:00Z",
            decision="execute",
            dramaturgical_function="contrast",
            executed=False,
            blocked_reason="media_density_too_high",
        ),
    ]
    summary = build_analysis_summary(entries)
    assert summary.total_decisions == 3
    assert summary.executed_count == 2
    assert summary.blocked_count == 1
    assert summary.silence_count == 1
    assert summary.silence_ratio == 0.333
    assert summary.function_counts["space"] == 1
    assert summary.blocked_reasons["media_density_too_high"] == 1
