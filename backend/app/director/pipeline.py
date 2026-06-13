import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import Lock

from app.core.config import settings
from app.director.cues.cue_models import DramaturgyDecision, OscCommand, ScheduledCue
from app.director.cues.scheduler import CueScheduler
from app.director.cues.safety import SafetyState, get_safety_state
from app.director.dialogue.models import DialogueEvent, DialogueSpeaker
from app.director.dramaturgy.engine import DramaturgyEngine
from app.director.media.database import MediaDatabase
from app.director.outputs.lighting import LightingBridge
from app.director.outputs.logger import DirectorLogger
from app.director.outputs.osc_commands import build_osc_commands, send_osc_commands
from app.director.outputs.sound import SoundBridge
from app.director.outputs.touchdesigner import TouchDesignerBridge

CUE_STAGGER_SECONDS = 0.15


@dataclass
class DirectorResult:
    event: DialogueEvent
    decision: DramaturgyDecision
    executed: bool
    blocked_reason: str | None = None
    scheduled_cue: ScheduledCue | None = None
    planned_commands: list[OscCommand] = field(default_factory=list)
    osc_commands: list[OscCommand] = field(default_factory=list)


@dataclass
class DirectorState:
    last_event: DialogueEvent | None = None
    last_decision: DramaturgyDecision | None = None
    last_result: DirectorResult | None = None
    last_osc_commands: list[OscCommand] = field(default_factory=list)
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

    def plan(self, event: DialogueEvent) -> DirectorResult:
        decision = self.engine.decide(event)
        allowed, blocked_reason = self.scheduler.can_execute(decision)
        dry_run = settings.osc_dry_run or self.safety.emergency_stop_active
        planned = build_osc_commands(decision, dry_run=dry_run)

        if not allowed:
            planned = []

        scheduled = ScheduledCue(
            decision=decision,
            scheduled_at=datetime.now(UTC),
            executed=False,
            blocked_reason=blocked_reason,
        )
        result = DirectorResult(
            event=event,
            decision=decision,
            executed=False,
            blocked_reason=blocked_reason,
            scheduled_cue=scheduled,
            planned_commands=planned,
            osc_commands=[],
        )
        self._store_result(result, log_executed=False)
        return result

    def execute(
        self,
        decision: DramaturgyDecision,
        *,
        force: bool = False,
        stagger: bool = True,
    ) -> DirectorResult:
        allowed, blocked_reason = self.scheduler.can_execute(decision)
        if force:
            allowed = True
            blocked_reason = None

        dry_run = settings.osc_dry_run or self.safety.emergency_stop_active
        planned = build_osc_commands(decision, dry_run=dry_run)
        osc_commands: list[OscCommand] = []

        if allowed and planned:
            osc_commands = self._execute_commands(planned, stagger=stagger)
            self.scheduler.mark_executed(decision)

        event = self.state.last_event or DialogueEvent(
            speaker=DialogueSpeaker.AI_A,
            text="(script beat)",
            topic="",
            mood=decision.mood,
            intensity=decision.intensity,
            tags=decision.tags,
            timestamp=decision.timestamp,
        )

        result = DirectorResult(
            event=event,
            decision=decision,
            executed=allowed and bool(osc_commands),
            blocked_reason=blocked_reason,
            planned_commands=planned,
            osc_commands=osc_commands,
        )
        self._store_result(result, log_executed=result.executed)
        return result

    def process(self, event: DialogueEvent, *, force: bool = False) -> DirectorResult:
        if settings.director_execute_mode == "sequenced" and not force:
            return self.plan(event)
        planned_result = self.plan(event)
        if not force and planned_result.blocked_reason:
            return planned_result
        return self.execute(planned_result.decision, force=force)

    def _execute_commands(self, commands: list[OscCommand], *, stagger: bool) -> list[OscCommand]:
        bridges = {
            "touchdesigner": self.touchdesigner,
            "sound": self.sound,
            "lighting": self.lighting,
        }
        sent: list[OscCommand] = []
        last_bridge: str | None = None
        for cmd in commands:
            if stagger and last_bridge is not None and cmd.bridge != last_bridge:
                time.sleep(CUE_STAGGER_SECONDS)
            last_bridge = cmd.bridge
            send_osc_commands([cmd], bridges)
            sent.append(cmd)
        return sent

    def _store_result(self, result: DirectorResult, *, log_executed: bool) -> None:
        self.logger.log_event(
            result.event,
            result.decision,
            executed=log_executed and result.executed,
            blocked_reason=result.blocked_reason,
        )
        with self._lock:
            self.state.last_event = result.event
            self.state.last_decision = result.decision
            self.state.last_result = result
            if result.osc_commands:
                self.state.last_osc_commands = result.osc_commands
            self.state.history.append(result)
            self.state.history = self.state.history[-50:]

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
