from app.director.cues.cue_models import (
    CuePoint,
    CuePointTrigger,
    DramaturgyDecision,
    LightCue,
    SoundAction,
    SoundCue,
    VisualAction,
    VisualCue,
)
from app.director.dialogue.models import DialogueEvent
from app.director.media.database import MediaDatabase
from app.director.media.selector import MediaSelector


class DramaturgyEngine:
    def __init__(self, media_db: MediaDatabase | None = None) -> None:
        self.media_db = media_db or MediaDatabase()
        self.selector = MediaSelector(self.media_db)

    def decide(self, event: DialogueEvent) -> DramaturgyDecision:
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
        return decision

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
