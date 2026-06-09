from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import Lock

from app.core.config import settings
from app.director.cues.cue_models import DramaturgyDecision, ScheduledCue
from app.director.cues.scheduler import CueScheduler
from app.director.cues.safety import SafetyState, get_safety_state
from app.director.dialogue.models import DialogueEvent
from app.director.dramaturgy.engine import DramaturgyEngine
from app.director.media.database import MediaDatabase
from app.director.outputs.lighting import LightingBridge
from app.director.outputs.logger import DirectorLogger
from app.director.outputs.sound import SoundBridge
from app.director.outputs.touchdesigner import TouchDesignerBridge


@dataclass
class DirectorResult:
    event: DialogueEvent
    decision: DramaturgyDecision
    executed: bool
    blocked_reason: str | None = None
    scheduled_cue: ScheduledCue | None = None


@dataclass
class DirectorState:
    last_event: DialogueEvent | None = None
    last_decision: DramaturgyDecision | None = None
    last_result: DirectorResult | None = None
    history: list[DirectorResult] = field(default_factory=list)


class DirectorPipeline:
    def __init__(
        self,
        media_db: MediaDatabase | None = None,
        safety: SafetyState | None = None,
        touchdesigner: TouchDesignerBridge | None = None,
        sound: SoundBridge | None = None,
        lighting: LightingBridge | None = None,
        logger: DirectorLogger | None = None,
    ) -> None:
        self.media_db = media_db or MediaDatabase()
        self.safety = safety or get_safety_state()
        self.engine = DramaturgyEngine(self.media_db)
        self.scheduler = CueScheduler(self.media_db.rules, self.safety)
        self.touchdesigner = touchdesigner or TouchDesignerBridge()
        self.sound = sound or SoundBridge()
        self.lighting = lighting or LightingBridge(self.media_db)
        self.logger = logger or DirectorLogger()
        self.state = DirectorState()
        self._lock = Lock()

    def process(self, event: DialogueEvent, *, force: bool = False) -> DirectorResult:
        decision = self.engine.decide(event)
        allowed, blocked_reason = self.scheduler.can_execute(decision)

        if force:
            allowed = True
            blocked_reason = None

        executed = False
        if allowed:
            self._execute(decision)
            self.scheduler.mark_executed(decision)
            executed = True

        scheduled = ScheduledCue(
            decision=decision,
            scheduled_at=datetime.now(UTC),
            executed=executed,
            blocked_reason=blocked_reason,
        )
        result = DirectorResult(
            event=event,
            decision=decision,
            executed=executed,
            blocked_reason=blocked_reason,
            scheduled_cue=scheduled,
        )

        self.logger.log_event(event, decision, executed=executed, blocked_reason=blocked_reason)

        with self._lock:
            self.state.last_event = event
            self.state.last_decision = decision
            self.state.last_result = result
            self.state.history.append(result)
            self.state.history = self.state.history[-50:]

        return result

    def _execute(self, decision: DramaturgyDecision) -> None:
        dry_run = settings.osc_dry_run or self.safety.emergency_stop_active

        if decision.visual:
            visual = decision.visual
            if visual.action.value == "play_clip" and visual.clip_id:
                self.touchdesigner.play_clip(visual.clip_id, visual.opacity, visual.fade_time)
            elif visual.action.value == "fade_to_black":
                self.touchdesigner.blackout()
            elif visual.action.value == "stop_clip":
                self.touchdesigner.stop_clip()
            elif visual.action.value == "record_live" and visual.recording_id:
                self.touchdesigner.start_recording(visual.recording_id)
            elif visual.action.value == "play_recording" and visual.recording_id:
                self.touchdesigner.play_recording(visual.recording_id)

        if decision.sound:
            self.sound.execute(decision.sound, dry_run=dry_run)

        if decision.light:
            self.lighting.execute(decision.light, dry_run=dry_run)

    def emergency_stop(self) -> None:
        self.safety.emergency_stop()
        self.scheduler.clear_active()
        dry_run = settings.osc_dry_run
        self.touchdesigner.blackout()
        self.sound.stop_all(dry_run=dry_run)
        self.lighting.blackout(dry_run=dry_run)


_pipeline: DirectorPipeline | None = None


def get_director_pipeline() -> DirectorPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = DirectorPipeline()
    return _pipeline
