import json
import re
from typing import Any

from app.core.config import settings
from app.director.cues.cue_models import DecisionKind, DramaturgyDecision, resolve_light_scene_ids
from app.director.dialogue.models import DialogueEvent
from app.director.cues.cue_points import cue_point_is_active, min_cue_points_for_text, normalize_cue_points
from app.director.dramaturgy.engine import DramaturgyEngine
from app.director.dramaturgy.function_mapping import normalize_dramaturgical_function
from app.director.dramaturgy.reason_short import enrich_decision_metadata, is_valid_reason_short
from app.director.dramaturgy.rules_text import dramaturgy_rules_excerpt, load_dramaturgy_rules
from app.director.media.database import MediaDatabase
from app.director.dramaturgy.state import DramaturgyState
from app.services.ai_service import AIService
from app.services.video_cue_catalog import get_video_cue_catalog_service
from app.services.video_scope import VideoScope


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

    def catalog_allowlist(self, *, compact: bool = False, video_scope: VideoScope = "part2") -> dict[str, Any]:
        from app.services.extra_media_overrides import is_dramaturgy_active
        from app.services.video_scope import usable_dramaturgy_video_ids

        video_catalog = get_video_cue_catalog_service().load(video_scope)
        allowed_video_ids = usable_dramaturgy_video_ids(video_scope)
        videos = [v for v in self.media_db.videos if v.id in allowed_video_ids]
        lights = [
            s
            for s in self.media_db.light_scenes
            if s.id != "blackout" and is_dramaturgy_active("light", s.id)
        ]
        if compact:
            return {
                "videos": [{"id": v.id, "tags": v.tags[:4], "moods": v.moods[:3]} for v in videos],
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
                    for s in lights
                ],
            }
        return {
            "videos": [
                {"id": v.id, "path": v.path, "tags": v.tags, "moods": v.moods}
                for v in videos
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
                for s in lights
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
                "Ohne outputs[] und ohne projector: clip_id auf allen Beamern (RZ21, Adam, Eva, LED), sofern in der OSC-Liste vorhanden.",
                "Teil 1: nur Atmosphären-Clips (OSCBefehllisteOhneAvatare). Teil 2: zusätzlich Erzähler-Avatare (Inge, Sebastian, …).",
                "Pflicht-Begleitvideo: bonnie und clyde mehrmals als OSC-Atmosphäre in der Aufführung — nicht nur einmal, nicht dauernd.",
                "Nur ein Beamer: visual.projector setzen oder outputs[] mit genau einem output_id.",
                "Licht: nur scene_id aus lights[] — Kanäle laut Kanal-Übersicht.",
                "Licht kombinieren: light.scene_ids mit mehreren IDs (z. B. [\"musiker\", \"warme_buehnenflaeche\"]).",
                "Pflichtlicht Avatare: Bei SCH4_Thomas und WO2_Branko muss klaviertasten in light.scene_ids enthalten sein (zusätzlich zu anderen Stimmungen).",
                "Jeder neue Licht-Cue ersetzt den vorherigen (Key Out, dann neue Kanäle/Gruppen).",
                "Lichtdesign: Viele Lichtwechsel sind gut — aber nie Rapid-Fire (mindestens ~8s Abstand früh, kürzer erst im Chaos).",
                "Licht früh/niedrige Intensität: lange Fades (5–8s), weiche Basis (gegenlicht_weich, warme_buehnenflaeche, luster_treppen).",
                "Licht Chaos/hohe Intensität: kurze Fades/Cuts, harte Kontraste (seitenlicht_hart, blendung_*) erlaubt.",
                "Lichtwechsel begründen; Look-Familie weiterentwickeln statt wildes Blinken.",
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
        dramaturgy_state: DramaturgyState | dict[str, object] | None = None,
    ) -> DramaturgyDecision:
        state_snapshot = self._state_snapshot(dramaturgy_state)
        if settings.director_dramaturgy_mode == "rules":
            state_obj = dramaturgy_state if isinstance(dramaturgy_state, DramaturgyState) else None
            return self.rule_engine.decide(event, dramaturgy_state=state_obj)

        try:
            raw = await self._call_llm(
                event,
                model=model,
                discussion_context=discussion_context,
                dramaturgy_state=state_snapshot,
            )
            decision = self._parse_decision(raw, event)
            self.validate_decision(decision, text=event.text)
            return enrich_decision_metadata(decision)
        except (DramaturgyValidationError, json.JSONDecodeError, KeyError, ValueError):
            state_obj = dramaturgy_state if isinstance(dramaturgy_state, DramaturgyState) else None
            return self.rule_engine.decide(event, dramaturgy_state=state_obj)

    @staticmethod
    def _state_snapshot(
        dramaturgy_state: DramaturgyState | dict[str, object] | None,
    ) -> dict[str, object]:
        if dramaturgy_state is None:
            return {}
        if isinstance(dramaturgy_state, DramaturgyState):
            return dramaturgy_state.snapshot()
        return dict(dramaturgy_state)

    async def _call_llm(
        self,
        event: DialogueEvent,
        *,
        model: str,
        discussion_context: str,
        dramaturgy_state: dict[str, object] | None = None,
    ) -> str:
        catalog = json.dumps(self.catalog_allowlist(compact=True), ensure_ascii=False)
        rules = dramaturgy_rules_excerpt(max_chars=settings.dramaturgy_rules_excerpt_chars)
        min_points = min_cue_points_for_text(event.text)
        state_json = json.dumps(dramaturgy_state or {}, ensure_ascii=False)
        system = (
            "Du arbeitest als professionelle Theaterdramaturgin und Live-Medienkünstlerin. "
            "Deine Aufgabe ist nicht, jede Textstelle zu bebildern oder zu vertonen — "
            "du gestaltest über längere Zeit eine abwechslungsreiche dramaturgische Entwicklung. "
            "Du arbeitest mit Video, Sound und Licht; alle Entscheidungen müssen als OSC-Cues "
            "formulierbar sein. "
            "Berücksichtige: aktuellen Text, Szene, laufende Ebenen, Medien-Dichte, Wiederholungen, "
            "Verständlichkeit der Sprache, die Möglichkeit nichts zu tun, und Material zu beenden. "
            "Der Live-Zustand (DramaturgyState) ist verbindlich: bei hoher Dichte eher space/release/"
            "fade_to_black/stop_clip wählen statt neue Starts. "
            "Bevorzuge präzise Entscheidungen gegenüber vielen. "
            "Licht: viele Wechsel ok, aber mit Abstand — keine Rapid-Fire-Signale; "
            "lange Fades am Anfang, schnelle Schnitte erst bei Chaos. "
            "Überraschung durch Kontrast, Timing, Wiederaufnahme oder Reduktion — nicht durch Zufall. "
            "Gib für jede Entscheidung reason_short: höchstens ein kurzer deutscher Satz mit dramaturgischer Funktion. "
            "dramaturgical_function: support|contrast|intensification|release|transition|recall|disruption|"
            "foreshadowing|space. "
            "decision_kind: execute|modify|stop|hold|none — none/space für bewusstes Nichtstun. "
            "Wähle NUR IDs aus der Medien-Allowlist. Keine Hardware-Befehle. "
            "Antworte ausschließlich mit gültigem JSON ohne Markdown.\n\n"
            f"=== DRAMATURGIE-REGELWERK ===\n{rules}"
        )
        user = (
            f"Textabschnitt:\n{event.text}\n\n"
            f"Thema/Kontext: {event.topic}\n"
            f"Stimmung: {event.mood}, Intensität: {event.intensity}, Tags: {event.tags}\n\n"
            f"Live-DramaturgyState:\n{state_json}\n\n"
            f"Dramaturgie-Diskussion:\n{discussion_context or '(keine)'}\n\n"
            f"Medien-Allowlist:\n{catalog}\n\n"
            f"Mindestens {min_points} cue_points für diesen Abschnitt, ODER decision_kind=none mit Begründung.\n"
            "JSON-Schema:\n"
            '{"dramaturgical_reading":"...","decision_kind":"execute","reason_short":"...",'
            '"dramaturgical_function":"support","confidence":0.8,"cue_points":['
            '{"trigger":"start","time_offset_sec":0,"function":"support","intensity":0.45,'
            '"visual":{"action":"play_clip","clip_id":"clyde","opacity":0.8,"fade_time":4},'
            '"sound":{"action":"trigger_cue","cue_id":"...","volume":0.4},'
            '"light":{"action":"set_scene","scene_id":"...","fade_time":5,"intensity":0.65}},'
            '{"trigger":"keyword","keyword":"Schuld","function":"contrast","intensity":0.7,...}'
            '],"reason":"...","tags":[],"mood":"...","intensity":0.5,"timestamp":0,'
            '"performance_speakers":["AI_A","AI_B"]}\n'
            'Beispiel Nichtstun: {"decision_kind":"none","dramaturgical_function":"space",'
            '"reason_short":"Lässt den neuen Gedanken ohne mediale Begleitung beginnen.",'
            '"confidence":0.88,"cue_points":[],"reason":"...","mood":"...","intensity":0.5,"timestamp":0}\n'
            'Beispiel Entlastung: {"decision_kind":"modify","dramaturgical_function":"release",'
            '"reason_short":"Blendet das Bild aus, damit der nächste Satz freier steht.",'
            '"cue_points":[{"trigger":"start","function":"release","visual":'
            '{"action":"fade_to_black","fade_time":3}}],"mood":"...","intensity":0.4,"timestamp":0}'
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
        if "decision_kind" in data and isinstance(data["decision_kind"], str):
            data["decision_kind"] = data["decision_kind"].lower()
        if "dramaturgical_function" in data and isinstance(data["dramaturgical_function"], str):
            parsed_fn = normalize_dramaturgical_function(data["dramaturgical_function"])
            if parsed_fn:
                data["dramaturgical_function"] = parsed_fn.value
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

        if decision.decision_kind == DecisionKind.NONE:
            if not decision.reason_short and not decision.reason:
                raise DramaturgyValidationError("none decision requires reason_short")
            if decision.reason_short and not is_valid_reason_short(decision.reason_short):
                raise DramaturgyValidationError("invalid reason_short for none decision")
            return

        if decision.reason_short and not is_valid_reason_short(decision.reason_short):
            raise DramaturgyValidationError("invalid reason_short")

        from app.services.extra_media_overrides import is_dramaturgy_active
        from app.services.video_scope import usable_dramaturgy_video_ids

        video_ids = usable_dramaturgy_video_ids("part2")
        recording_ids = {r.id for r in self.media_db.recordings}
        sound_ids = {s.id for s in self.media_db.dramaturgy_sounds}
        light_ids = {
            s.id
            for s in self.media_db.light_scenes
            if s.id != "blackout" and is_dramaturgy_active("light", s.id)
        }
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
