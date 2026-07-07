"""Tests for background OSC command queue."""

from unittest.mock import patch

import pytest

from app.core.config import settings
from app.director.cues.cue_models import OscCommand
from app.director.outputs import osc_queue as osc_queue_mod
from app.director.outputs.osc_queue import get_osc_command_queue


@pytest.fixture
def isolated_queue(monkeypatch: pytest.MonkeyPatch) -> None:
    osc_queue_mod._queue = None
    monkeypatch.setattr(settings, "director_osc_queue", True)


def test_osc_queue_returns_before_send_completes(isolated_queue: None) -> None:
    sent: list[OscCommand] = []

    def slow_send(
        commands: list[OscCommand],
        *,
        stagger: bool,
        bridges: dict,
    ) -> list[OscCommand]:
        import time

        time.sleep(0.2)
        sent.extend(commands)
        return commands

    queue = get_osc_command_queue()
    cmd = OscCommand(
        bridge="pixera",
        host="127.0.0.1",
        port=8990,
        address="/pixera/args/cue/apply",
        args=["Test"],
        dry_run=True,
    )
    with patch("app.director.outputs.osc_queue.send_osc_batch", side_effect=slow_send):
        returned = queue.enqueue([cmd], stagger=False, bridges={}, wait=False)
        assert returned == [cmd]
        assert sent == []
        queue.flush(timeout=2.0)
    assert sent == [cmd]


def test_osc_queue_wait_blocks_until_sent(isolated_queue: None) -> None:
    calls: list[str] = []

    def record_send(
        commands: list[OscCommand],
        *,
        stagger: bool,
        bridges: dict,
    ) -> list[OscCommand]:
        calls.append(commands[0].address)
        return commands

    queue = get_osc_command_queue()
    cmd = OscCommand(
        bridge="pixera",
        host="127.0.0.1",
        port=8990,
        address="/pixera/args/cue/apply",
        args=["Wait"],
        dry_run=True,
    )
    with patch("app.director.outputs.osc_queue.send_osc_batch", side_effect=record_send):
        sent = queue.enqueue([cmd], stagger=False, bridges={}, wait=True, timeout=2.0)
    assert sent == [cmd]
    assert calls == ["/pixera/args/cue/apply"]
