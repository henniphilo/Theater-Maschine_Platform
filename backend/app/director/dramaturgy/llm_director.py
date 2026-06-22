import json
import re
from typing import Any

from app.core.config import settings
from app.director.cues.cue_models import DramaturgyDecision, resolve_light_scene_ids
from app.director.dialogue.models import DialogueEvent
from app.director.cues.cue_points import cue_point_is_active, min_cue_points_for_text, normalize_cue_points
from app.director.dramaturgy.engine import DramaturgyEngine
from app.director.dramaturgy.rules_text import dramaturgy_rules_excerpt, load_dramaturgy_rules
from app.director.media.database import MediaDatabase
from app.services.ai_service import AIService
from app.services.video_cue_catalog import get_video_cue_catalog_service


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

    def catalog_allowlist(self, *, compact: bool = False) -> dict[str, Any]:
        video_catalog = get_video_cue_catalog_service().load()
        if compact:
            return {
                "videos": [{"id": v.id, "tags": v.tags[:4], "moods": v.moods[:3]} for v in self.media_db.videos],
                "projectors": [
                    {"id": p.id, "name": p.name, "pixera_prefix": p.pixera_prefix}
                    for p in video_catalog.projectors
                ],
                "recordings": [{"id": r.id, "tags": r.tags[:4]} for r in self.media_db.recordings],
                "sounds": [
                    {
                        "id": s.id,
                        "soundname": s.soundname or s.label,
                        "action": s.action,
                        "tags": s.tags[:4],
                        "moods": s.moods[:3],
                        "midi_note": s.midi_note,
                    }
                    for s in self.media_db.dramaturgy_sounds
                ],
                "lights": [
                    {"id": s.id, "moods": s.moods[:3], "channels": s.channels[:6]}
                    for s in self.media_db.light_scenes
                    if s.id != "blackout"
                ],
            }
        return {
            "videos": [
                {"id": v.id, "path": v.path, "tags": v.tags, "moods": v.moods}
                for v in self.media_db.videos
            ],
            "projectors": [
                {
                    "id": p.id,
                    "name": p.name,
                    "pixera_prefix": p.pixera_prefix,
                    "description": p.description,
                }
                for p in video_catalog.projectors
            ],
            "recordings": [
                {"id": r.id, "path": r.path, "tags": r.tags}
                for r in self.media_db.recordings
            ],
            "sounds": [
                {
                    "id": s.id,
                    "soundname": s.soundname or s.label,
                    "action": s.action,
                    "description": s.description,
                    "midi_note": s.midi_note,
                    "channel": s.channel,
                    "ableton_hint": s.ableton_hint,
                    "tags": s.tags,
                    "moods": s.moods,
                }
                for s in self.media_db.dramaturgy_sounds
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
                "Video: mehrere Projektoren (projectors[]) erlaubt — visual.outputs mit output_id + clip_id.",
                "Gleiches Video auf mehreren Projektoren: gleiche clip_id, verschiedene output_id.",
                "Unterschiedliche Videos: pro output_id eigene clip_id in outputs[].",
                "Ohne outputs[] gilt clip_id nur für RZ21 (Frontprojektor).",
                "Licht: nur scene_id aus lights[] — Kanäle laut Kanal-Übersicht.",
                "Licht kombinieren: light.scene_ids mit mehreren IDs (z. B. [\"musiker\", \"warme_buehnenflaeche\"]).",
                "Jeder neue Licht-Cue ersetzt den vorherigen (Key Out, dann neue Kanäle/Gruppen).",
                "Licht-Intensität: light.intensity 0.0–1.0 (0.35 = dezent, 1.0 = voll); fehlt → cue_point.intensity.",
                "Sound: nur cue_id aus sounds[] (play / fade_in / fade_out / out) — MIDI an Ableton.",
                "Sound sofort aus (ein Layer): cue_id mit _out (z. B. kaefigecho_out).",
                "Alle Sounds sofort aus: cue_id alle_sounds_cut.",
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
        catalog = json.dumps(self.catalog_allowlist(compact=True), ensure_ascii=False)
        rules = dramaturgy_rules_excerpt(max_chars=settings.dramaturgy_rules_excerpt_chars)
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
            "performance_speakers: 1–3 Stimmen aus [AI_A, AI_B, narrator] für den Stücktext. "
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
            '"visual":{"action":"play_clip","clip_id":"clyde","outputs":[{"output_id":"rz21","clip_id":"clyde"},{"output_id":"adam","clip_id":"black"}],"opacity":0.8,"fade_time":4},'
            '"sound":{"action":"trigger_cue","cue_id":"...","volume":0.4},'
            '"light":{"action":"set_scene","scene_id":"...","fade_time":5,"intensity":0.65}},'
            '{"trigger":"keyword","keyword":"Schuld","function":"entlarven","intensity":0.7,...}'
            '],"reason":"...","tags":[],"mood":"...","intensity":0.5,"timestamp":0,'
            '"performance_speakers":["AI_A","AI_B"]}'
        )
        return await self.ai.generate(
            "openai",
            model,
            [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            max_tokens=settings.dramaturgy_decision_max_tokens,
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
        sound_ids = {s.id for s in self.media_db.dramaturgy_sounds}
        light_ids = {s.id for s in self.media_db.light_scenes}
        output_ids = {p.id for p in get_video_cue_catalog_service().load().projectors}

        def _validate_visual(visual, *, context: str) -> None:
            if not visual:
                return
            if visual.outputs:
                for assignment in visual.outputs:
                    if assignment.output_id not in output_ids:
                        raise DramaturgyValidationError(
                            f"Unknown output_id: {assignment.output_id} ({context})"
                        )
                    clip_id = assignment.clip_id or visual.clip_id
                    if clip_id and clip_id not in video_ids:
                        raise DramaturgyValidationError(f"Unknown clip_id: {clip_id} ({context})")
            if visual.action == VisualAction.PLAY_RECORDING:
                if visual.recording_id and visual.recording_id not in recording_ids:
                    raise DramaturgyValidationError(
                        f"Unknown recording_id: {visual.recording_id} ({context})"
                    )
            elif visual.clip_id and visual.clip_id not in video_ids:
                raise DramaturgyValidationError(f"Unknown clip_id: {visual.clip_id} ({context})")

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
                _validate_visual(point.visual, context=f"cue_point {index}")

            if point.sound and point.sound.cue_id and point.sound.cue_id not in sound_ids:
                raise DramaturgyValidationError(f"Unknown cue_id: {point.sound.cue_id}")
            if point.light:
                for sid in resolve_light_scene_ids(point.light):
                    if sid not in light_ids:
                        raise DramaturgyValidationError(f"Unknown scene_id: {sid} (cue_point {index})")

        if decision.visual:
            _validate_visual(decision.visual, context="decision")
        if decision.sound and decision.sound.cue_id and decision.sound.cue_id not in sound_ids:
            raise DramaturgyValidationError(f"Unknown cue_id: {decision.sound.cue_id}")
        if decision.light:
            for sid in resolve_light_scene_ids(decision.light):
                if sid not in light_ids:
                    raise DramaturgyValidationError(f"Unknown scene_id: {sid}")

        allowed_speakers = {"AI_A", "AI_B", "narrator"}
        if decision.performance_speakers:
            invalid = [s for s in decision.performance_speakers if s not in allowed_speakers]
            if invalid:
                raise DramaturgyValidationError(f"Unknown performance_speakers: {invalid}")
