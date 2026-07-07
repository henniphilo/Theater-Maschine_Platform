"""Tests for Teil-2 prepare service."""

from __future__ import annotations

import asyncio

import pytest

from app.schemas.inszenierung import SceneCorpus
from app.services.teil2_prepare_service import Teil2PrepareService


def test_prepare_builds_plan_with_segments_and_dramaturgy(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.director_dramaturgy_mode", "rules")

    corpus = SceneCorpus(
        id="test-corpus",
        title="Test",
        script_text=(
            "23. Der Delphin? Man hat mich dazu gezwungen.\n\n"
            "24. Der Bärenklauer übernimmt.\n\n"
            "25. Das Lamm Gottes,\n"
        ),
    )
    service = Teil2PrepareService()
    gesamtkonzept, plan = asyncio.run(service.prepare(corpus, performance_speaker="narrator"))

    assert gesamtkonzept.thesis
    assert len(plan.sentences) >= 3
    assert plan.performance_speaker == "narrator"
    assert plan.dramaturgy.cue_points
    assert len(plan.dramaturgy.cue_points) >= max(2, len(plan.avatar_segments))
    light_points = [p for p in plan.dramaturgy.cue_points if p.light is not None]
    assert len(light_points) >= len(plan.sentences)
    light_scene_ids = {p.light.scene_id for p in light_points if p.light and p.light.scene_id}
    assert len(light_scene_ids) >= 2
    atmosphere_points = [
        p
        for p in plan.dramaturgy.cue_points
        if p.visual is not None and p.visual.video_type == "atmosphere"
    ]
    assert len(atmosphere_points) >= 1
    assert plan.model_dump_json()


def test_prepare_requires_script_text():
    corpus = SceneCorpus(id="empty", title="Leer")
    service = Teil2PrepareService()
    with pytest.raises(ValueError, match="Kein Aufführungstext"):
        asyncio.run(service.prepare(corpus))
