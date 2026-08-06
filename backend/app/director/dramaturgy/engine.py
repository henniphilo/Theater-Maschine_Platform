from app.director.cues.cue_models import (
    CuePoint,
    CuePointTrigger,
    DecisionKind,
    DramaturgicalFunction,
    DramaturgyDecision,
    LightCue,
    SoundAction,
    SoundCue,
    VisualAction,
    VisualCue,
)
from app.director.dialogue.models import DialogueEvent
from app.director.dramaturgy.reason_short import enrich_decision_metadata
from app.director.dramaturgy.state import DramaturgyState
from app.director.media.database import MediaDatabase
from app.director.media.selector import MediaSelector


class DramaturgyEngine:
    def __init__(self, media_db: MediaDatabase | None = None) -> None:
        self.media_db = media_db or MediaDatabase()
        self.selector = MediaSelector(self.media_db)

    def decide(
        self,
        event: DialogueEvent,
        *,
        dramaturgy_state: DramaturgyState | None = None,
    ) -> DramaturgyDecision:
        state = dramaturgy_state
        if state is not None:
            state.apply_text_context(
                text=event.text,
                mood=event.mood,
                intensity=event.intensity,
                tags=list(event.tags),
            )
            # Prefer silence / release when the stage is already dense.
            if state.total_media_density >= 0.72 and event.intensity < 0.55:
                return enrich_decision_metadata(
                    DramaturgyDecision(
                        decision_kind=DecisionKind.NONE,
                        dramaturgical_function=DramaturgicalFunction.SPACE,
                        reason_short="Lässt den Text ohne weitere Medienlage atmen.",
                        reason=(
                            f"Medien-Dichte {state.total_media_density:.2f} — "
                            "bewusstes Nichtstun statt zusätzlicher Starts."
                        ),
                        tags=event.tags,
                        mood=event.mood,
                        intensity=event.intensity,
                        timestamp=event.timestamp,
                        cue_points=[],
                    )
                )
            if state.total_media_density >= 0.85:
                return enrich_decision_metadata(
                    DramaturgyDecision(
                        decision_kind=DecisionKind.MODIFY,
                        dramaturgical_function=DramaturgicalFunction.RELEASE,
                        reason_short="Reduziert die Bildfläche, damit der Text wieder Raum bekommt.",
                        reason="Hohe Video-Dichte — Fade to Black als dramaturgische Entlastung.",
                        tags=event.tags,
                        mood=event.mood,
                        intensity=event.intensity,
                        timestamp=event.timestamp,
                        visual=VisualCue(action=VisualAction.FADE_TO_BLACK, fade_time=3.0),
                        cue_points=[
                            CuePoint(
                                trigger=CuePointTrigger.START,
                                function="release",
                                intensity=max(0.2, event.intensity * 0.5),
                                visual=VisualCue(action=VisualAction.FADE_TO_BLACK, fade_time=3.0),
                            )
                        ],
                    )
                )

        video = self.selector.select_video(event.tags, event.mood, event.intensity)
        sound = self.selector.select_sound(event.tags, event.mood, event.intensity)
        light = self.selector.select_light(event.mood, event.intensity)

        reason = self._build_reason(event, video, sound, light)

        visual = None
        if video:
            visual = VisualCue(
                action=VisualAction.PLAY_CLIP,
                clip_id=video.id,
                blend=video.preferred_blend,
                opacity=0.85 if event.intensity > 0.7 else 0.7,
                fade_time=2.0 if event.intensity > 0.8 else 4.0,
            )

        sound_cue = None
        if sound:
            sound_cue = SoundCue(
                action=SoundAction.TRIGGER_CUE,
                cue_id=sound.id,
                volume=round(0.4 + event.intensity * 0.4, 2),
            )

        light_cue = None
        if light:
            light_cue = LightCue(
                scene_id=light.id,
                fade_time=light.fade_time,
                intensity=round(0.25 + event.intensity * 0.75, 2),
            )

        decision = DramaturgyDecision(
            visual=visual,
            sound=sound_cue,
            light=light_cue,
            reason=reason,
            tags=event.tags,
            mood=event.mood,
            intensity=event.intensity,
            timestamp=event.timestamp,
            cue_points=[
                CuePoint(
                    trigger=CuePointTrigger.START,
                    function="verstärken",
                    intensity=event.intensity,
                    visual=visual,
                    sound=sound_cue,
                    light=light_cue,
                )
            ],
        )
        return enrich_decision_metadata(decision)

    @staticmethod
    def _build_reason(event: DialogueEvent, video, sound, light) -> str:
        parts = [
            f"Text thematisiert {', '.join(event.tags)} mit Stimmung „{event.mood}“ "
            f"(Intensität {event.intensity:.2f})."
        ]
        if video:
            parts.append(f"Video: {video.id}.")
        if sound:
            parts.append(f"Sound: {sound.id}.")
        if light:
            parts.append(f"Licht: {light.id}.")
        return " ".join(parts)
