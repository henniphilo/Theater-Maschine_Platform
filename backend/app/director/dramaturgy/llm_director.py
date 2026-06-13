import json
import re
from typing import Any

from app.core.config import settings
from app.director.cues.cue_models import DramaturgyDecision
from app.director.dialogue.models import DialogueEvent
from app.director.cues.cue_points import cue_point_is_active, min_cue_points_for_text, normalize_cue_points
from app.director.dramaturgy.engine import DramaturgyEngine
from app.director.dramaturgy.rules_text import dramaturgy_rules_excerpt, load_dramaturgy_rules
from app.director.media.database import MediaDatabase
from app.services.ai_service import AIService


class DramaturgyValidationError(ValueError):
    pass


class LLMDirector:
    def __init__(
        self,
        media_db: MediaDatabase | None = None,
        ai_service: AIService | None = None,
    ) -> None:
        self.media_db = media_db or MediaDatabase()
        self.ai = ai_service or AIService()
        self.rule_engine = DramaturgyEngine(self.media_db)

    def catalog_allowlist(self) -> dict[str, Any]:
        return {
            "videos": [
                {"id": v.id, "path": v.path, "tags": v.tags, "moods": v.moods}
                for v in self.media_db.videos
            ],
            "recordings": [
                {"id": r.id, "path": r.path, "tags": r.tags}
                for r in self.media_db.recordings
            ],
            "sounds": [
                {"id": s.id, "path": s.path, "tags": s.tags, "moods": s.moods, "dummy": True}
                for s in self.media_db.sounds
            ],
            "lights": [
                {
                    "id": s.id,
                    "description": s.description,
                    "location": s.location,
                    "channels": s.channels,
                    "fixtures": s.fixtures,
                    "moods": s.moods,
                }
                for s in self.media_db.light_scenes
                if s.id != "blackout"
            ],
            "light_inventory_source": self.media_db.light_inventory.get(
                "source", "media/light/Kanal Übersicht.xlsx"
            ),
            "allowed_visual_actions": ["play_clip", "play_recording", "fade_to_black", "stop_clip"],
            "allowed_sound_actions": ["trigger_cue", "stop_cue", "set_volume"],
            "allowed_light_actions": ["set_scene", "fade_blackout", "pulse"],
            "rules": [
                "Vollständiges Regelwerk: docs/dramaturgy_rules.md",
                "Nur clip_id aus videos[] oder recording_id aus recordings[] — keine erfundenen IDs.",
                "Licht: nur scene_id aus lights[] — Kanäle laut Kanal-Übersicht.",
                "Sound: nur dummy_* Cues bis echte Audiofiles vorliegen.",
            ],
            "rules_digest": load_dramaturgy_rules()[:500],
        }

    async def decide(
        self,
        event: DialogueEvent,
        *,
        model: str = "gpt-4o",
        discussion_context: str = "",
    ) -> DramaturgyDecision:
        if settings.director_dramaturgy_mode == "rules":
            return self.rule_engine.decide(event)

        try:
            raw = await self._call_llm(event, model=model, discussion_context=discussion_context)
            decision = self._parse_decision(raw, event)
            self.validate_decision(decision, text=event.text)
            return decision
        except (DramaturgyValidationError, json.JSONDecodeError, KeyError, ValueError):
            return self.rule_engine.decide(event)

    async def _call_llm(
        self,
        event: DialogueEvent,
        *,
        model: str,
        discussion_context: str,
    ) -> str:
        catalog = json.dumps(self.catalog_allowlist(), ensure_ascii=False)
        rules = dramaturgy_rules_excerpt()
        min_points = min_cue_points_for_text(event.text)
        system = (
            "Du bist eine Theater-Regisseurin für die Bühne Unter Tieren. "
            "Du arbeitest ausschließlich mit Video, Sound und Licht — alle Entscheidungen "
            "müssen als OSC-Cues formulierbar sein. "
            "Halte dich strikt an das Dramaturgie-Regelwerk unten. "
            "Wähle NUR IDs aus der Medien-Allowlist. "
            "Pro Textabschnitt: mehrere cue_points (start, keyword, sentence_end, time). "
            "Jeder cue_point braucht visual, sound UND light — aktiv oder bewusst aus "
            "(stop_clip, stop_cue, fade_blackout). "
            "Keine Illustration, keine Schauspielanweisungen. "
            "Antworte ausschließlich mit gültigem JSON ohne Markdown.\n\n"
            f"=== DRAMATURGIE-REGELWERK ===\n{rules}"
        )
        user = (
            f"Textabschnitt:\n{event.text}\n\n"
            f"Thema/Kontext: {event.topic}\n"
            f"Stimmung: {event.mood}, Intensität: {event.intensity}, Tags: {event.tags}\n\n"
            f"Dramaturgie-Diskussion:\n{discussion_context or '(keine)'}\n\n"
            f"Medien-Allowlist:\n{catalog}\n\n"
            f"Mindestens {min_points} cue_points für diesen Abschnitt.\n"
            "JSON-Schema:\n"
            '{"dramaturgical_reading":"...","cue_points":['
            '{"trigger":"start","time_offset_sec":0,"function":"überlagern","intensity":0.45,'
            '"visual":{"action":"play_clip","clip_id":"...","opacity":0.8,"fade_time":4},'
            '"sound":{"action":"trigger_cue","cue_id":"...","volume":0.4},'
            '"light":{"action":"set_scene","scene_id":"...","fade_time":5}},'
            '{"trigger":"keyword","keyword":"Schuld","function":"entlarven","intensity":0.7,...}'
            '],"reason":"...","tags":[],"mood":"...","intensity":0.5,"timestamp":0}'
        )
        return await self.ai.generate(
            "openai",
            model,
            [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            max_tokens=2000,
        )

    def _parse_decision(self, raw: str, event: DialogueEvent) -> DramaturgyDecision:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)
        data = json.loads(cleaned)
        data.setdefault("tags", event.tags)
        data.setdefault("mood", event.mood)
        data.setdefault("intensity", event.intensity)
        data.setdefault("timestamp", event.timestamp)
        decision = DramaturgyDecision.model_validate(data)
        return self._sync_legacy_fields(decision)

    def _sync_legacy_fields(self, decision: DramaturgyDecision) -> DramaturgyDecision:
        points = normalize_cue_points(decision)
        if points and not (decision.visual or decision.sound or decision.light):
            first = points[0]
            decision.visual = first.visual
            decision.sound = first.sound
            decision.light = first.light
        decision.cue_points = points
        return decision

    def validate_decision(self, decision: DramaturgyDecision, *, text: str = "") -> None:
        from app.director.cues.cue_models import VisualAction

        decision = self._sync_legacy_fields(decision)
        video_ids = {v.id for v in self.media_db.videos}
        recording_ids = {r.id for r in self.media_db.recordings}
        sound_ids = {s.id for s in self.media_db.sounds}
        light_ids = {s.id for s in self.media_db.light_scenes}

        points = decision.cue_points
        if not points:
            raise DramaturgyValidationError("At least one cue_point required")

        if text:
            required = min_cue_points_for_text(text)
            if len(points) < required:
                raise DramaturgyValidationError(
                    f"Need at least {required} cue_points, got {len(points)}"
                )

        for index, point in enumerate(points):
            if not cue_point_is_active(point):
                raise DramaturgyValidationError(f"cue_point {index} has no video/sound/light")

            if point.visual:
                visual = point.visual
                if visual.action == VisualAction.PLAY_RECORDING:
                    if visual.recording_id and visual.recording_id not in recording_ids:
                        raise DramaturgyValidationError(
                            f"Unknown recording_id: {visual.recording_id}"
                        )
                elif visual.clip_id and visual.clip_id not in video_ids:
                    raise DramaturgyValidationError(f"Unknown clip_id: {visual.clip_id}")
            if point.sound and point.sound.cue_id and point.sound.cue_id not in sound_ids:
                raise DramaturgyValidationError(f"Unknown cue_id: {point.sound.cue_id}")
            if point.light and point.light.scene_id and point.light.scene_id not in light_ids:
                raise DramaturgyValidationError(f"Unknown scene_id: {point.light.scene_id}")

        if decision.visual:
            visual = decision.visual
            if visual.action == VisualAction.PLAY_RECORDING:
                if visual.recording_id and visual.recording_id not in recording_ids:
                    raise DramaturgyValidationError(
                        f"Unknown recording_id: {visual.recording_id}"
                    )
            elif visual.clip_id and visual.clip_id not in video_ids:
                raise DramaturgyValidationError(f"Unknown clip_id: {visual.clip_id}")
        if decision.sound and decision.sound.cue_id and decision.sound.cue_id not in sound_ids:
            raise DramaturgyValidationError(f"Unknown cue_id: {decision.sound.cue_id}")
        if decision.light and decision.light.scene_id and decision.light.scene_id not in light_ids:
            raise DramaturgyValidationError(f"Unknown scene_id: {decision.light.scene_id}")
