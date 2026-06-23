import asyncio
from unittest.mock import MagicMock

from app.schemas.part1_selection import PreviewCue
from app.services.preview_executor import PreviewExecutor, preview_duration_sec


def test_preview_durations() -> None:
    assert preview_duration_sec("video") == 2.0
    assert preview_duration_sec("sound") == 3.0
    assert preview_duration_sec("light") == 3.0


def test_preview_executor_simulates_without_sending() -> None:
    preview = PreviewCue(medium="sound", medium_id="test_sound", duration_sec=0.01, osc_commands=[])
    executor = PreviewExecutor(pipeline=MagicMock())
    cmds = asyncio.run(executor.run_preview(preview))
    assert isinstance(cmds, list)
