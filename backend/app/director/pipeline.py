import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import RLock

from app.core.config import settings
from app.director.cues.cue_models import DramaturgyDecision, OscCommand, ScheduledCue
from app.director.cues.projector_state import ProjectorState
from app.director.cues.scheduler import CueScheduler
from app.director.cues.safety import SafetyState, get_safety_state
from app.director.dialogue.models import DialogueEvent, DialogueSpeaker
from app.director.dramaturgy.conflict_check import check_conflicts
from app.director.dramaturgy.engine import DramaturgyEngine
from app.director.dramaturgy.proposals import ProposalStore
from app.director.dramaturgy.reason_short import enrich_decision_metadata
from app.director.dramaturgy.state import DramaturgyState
from app.director.dramaturgy.trace import emit_dramaturgy_decision
from app.director.media.database import MediaDatabase
from app.director.outputs.lighting import LightingBridge
from app.director.outputs.logger import DirectorLogger
from app.director.outputs.osc_commands import build_osc_commands
from app.director.outputs.osc_queue import CUE_STAGGER_SECONDS, get_osc_command_queue, send_osc_batch
from app.director.outputs.pixera import PixeraBridge
from app.director.outputs.sound import SoundBridge
from app.director.outputs.touchdesigner import TouchDesignerBridge
from app.director.outputs.signal_trace import (
    RequestTrace,
    attach_command_traces,
    begin_request_trace,
    emit_signal_trace_event,
)
from app.director.run_state import get_director_run_state
from app.schemas.director import TraceContext
from app.services.avatar_required_lights import apply_avatar_required_lights
from app.services.teil2_dramaturgy_routing import (
    active_avatar_reserved_projectors,
    route_dramaturgy_away_from_projectors,
)

CUE_STAGGER_SECONDS = CUE_STAGGER_SECONDS  # re-export for tests
_execute_logger = logging.getLogger("theatermaschine.osc")


def _filter_decision_for_safety(decision: DramaturgyDecision, safety: SafetyState) -> DramaturgyDecision:
    """Drop disabled output bridges so one failed subsystem does not block the rest."""
    updates: dict[str, object] = {}
    if (not safety.lights_enabled or safety.performance_tryout) and decision.light:
        updates["light"] = None
    if not safety.sound_enabled and decision.sound:
        updates["sound"] = None
    if not safety.visuals_enabled and decision.visual:
        updates["visual"] = None
    if not updates:
        return decision
    filtered = decision.model_copy(deep=True)
    for key, value in updates.items():
        setattr(filtered, key, value)
    if filtered.cue_points:
        filtered.cue_points = [
            point.model_copy(
                update={
                    "light": None if not safety.lights_enabled or safety.performance_tryout else point.light,
                    "sound": None if not safety.sound_enabled else point.sound,
                    "visual": None if not safety.visuals_enabled else point.visual,
                }
            )
            for point in filtered.cue_points
        ]
    return filtered


def _effective_dry_run(safety: SafetyState) -> bool:
    return settings.osc_dry_run or safety.performance_tryout


def _route_dramaturgy_from_avatar_projectors(
    decision: DramaturgyDecision,
    projectors: ProjectorState,
) -> DramaturgyDecision:
    if not decision.visual and not decision.cue_points:
        return decision
    reserved = active_avatar_reserved_projectors(projectors)
    if not reserved:
        return decision
    seed = int(decision.timestamp or 0) % 10_000
    return route_dramaturgy_away_from_projectors(decision.model_copy(deep=True), reserved, seed=seed)


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
        pixera: PixeraBridge | None = None,
        sound: SoundBridge | None = None,
        lighting: LightingBridge | None = None,
        logger: DirectorLogger | None = None,
    ) -> None:
        self.media_db = media_db or MediaDatabase()
        self.safety = safety or get_safety_state()
        self.engine = DramaturgyEngine(self.media_db)
        self.scheduler = CueScheduler(self.media_db.rules, self.safety)
        self.touchdesigner = touchdesigner or TouchDesignerBridge()
        self.pixera = pixera or PixeraBridge()
        self.sound = sound or SoundBridge()
        self.lighting = lighting or LightingBridge(self.media_db)
        self.logger = logger or DirectorLogger()
        self.projectors = ProjectorState()
        self.state = DirectorState()
        self.dramaturgy_state = DramaturgyState()
        self.proposals = ProposalStore()
        self.run_state = get_director_run_state()
        self._lock = RLock()

    def plan(self, event: DialogueEvent) -> DirectorResult:
        self.dramaturgy_state.apply_text_context(
            text=event.text,
            mood=event.mood,
            intensity=event.intensity,
            tags=list(event.tags),
        )
        decision = enrich_decision_metadata(
            self.engine.decide(event, dramaturgy_state=self.dramaturgy_state)
        )
        conflict = check_conflicts(decision, self.dramaturgy_state)
        if not conflict.allowed and conflict.reason:
            blocked_reason = conflict.reason
            allowed = False
        else:
            allowed, blocked_reason = self.scheduler.can_execute(
                decision,
                dramaturgy_state=self.dramaturgy_state,
            )
        dry_run = settings.osc_dry_run or self.safety.emergency_stop_active
        planned = build_osc_commands(decision, dry_run=dry_run)

        if not allowed:
            planned = []

        self.proposals.create(decision, text_snippet=event.text)
        emit_dramaturgy_decision(
            decision,
            event=event,
            executed=False,
            blocked_reason=blocked_reason,
        )

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
        trace: TraceContext | None = None,
        request_trace: RequestTrace | None = None,
    ) -> DirectorResult:
        with self._lock:
            return self._execute_locked(
                decision,
                force=force,
                stagger=stagger,
                trace=trace,
                request_trace=request_trace,
            )

    def _execute_locked(
        self,
        decision: DramaturgyDecision,
        *,
        force: bool,
        stagger: bool,
        trace: TraceContext | None = None,
        request_trace: RequestTrace | None = None,
    ) -> DirectorResult:
        req_trace = request_trace or begin_request_trace(trace)
        if self.safety.emergency_stop_active:
            emit_signal_trace_event(
                "director.execute_blocked",
                status="blocked",
                blocked_reason="emergency_stop_active",
                request_trace=req_trace,
            )
            return self._emergency_blocked_result(decision, "(script beat)")

        decision = apply_avatar_required_lights(decision, self.projectors)
        decision = _filter_decision_for_safety(decision, self.safety)
        decision = enrich_decision_metadata(decision)
        decision = _route_dramaturgy_from_avatar_projectors(decision, self.projectors)
        conflict = check_conflicts(decision, self.dramaturgy_state)
        allowed, blocked_reason = self.scheduler.can_execute(
            decision,
            dramaturgy_state=self.dramaturgy_state,
        )
        if (
            not allowed
            and blocked_reason == "light_cue_too_soon"
            and (decision.visual or decision.sound)
        ):
            decision = decision.model_copy(deep=True, update={"light": None})
            allowed, blocked_reason = self.scheduler.can_execute(
                decision,
                dramaturgy_state=self.dramaturgy_state,
            )
        if not conflict.allowed and conflict.reason and not force:
            allowed = False
            blocked_reason = conflict.reason
        if force:
            allowed = True
            blocked_reason = None

        dry_run = _effective_dry_run(self.safety)
        planned = build_osc_commands(decision, dry_run=dry_run)
        emit_signal_trace_event(
            "signal.planned",
            status="planned",
            planned_command_count=len(planned),
            request_trace=req_trace,
        )
        if planned:
            planned = attach_command_traces(planned, req_trace)
            self._emit_command_built_events(planned, req_trace)
        osc_commands: list[OscCommand] = []

        if not allowed:
            emit_signal_trace_event(
                "director.execute_blocked",
                status="blocked",
                blocked_reason=blocked_reason,
                request_trace=req_trace,
            )
        elif allowed and planned:
            osc_commands = self._dispatch_commands(planned, stagger=stagger)
            self.scheduler.mark_executed(decision)
            self.dramaturgy_state.apply_decision(decision, executed=True)

        event = self.state.last_event or DialogueEvent(
            speaker=DialogueSpeaker.AI_A,
            text="(script beat)",
            topic="",
            mood=decision.mood,
            intensity=decision.intensity,
            tags=decision.tags,
            timestamp=decision.timestamp,
        )

        emit_dramaturgy_decision(
            decision,
            event=event,
            request_trace=req_trace,
            executed=allowed and bool(osc_commands),
            blocked_reason=blocked_reason,
            intensity_before=self.dramaturgy_state.scene_intensity,
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

    def execute_layered(
        self,
        decision: DramaturgyDecision,
        *,
        anarchy_level: float = 0.5,
        stack: bool = True,
        skip_interval_check: bool = True,
        stagger: bool = False,
        text_excerpt: str | None = None,
        trace: TraceContext | None = None,
        request_trace: RequestTrace | None = None,
    ) -> DirectorResult:
        with self._lock:
            return self._execute_layered_locked(
                decision,
                anarchy_level=anarchy_level,
                stack=stack,
                skip_interval_check=skip_interval_check,
                stagger=stagger,
                text_excerpt=text_excerpt,
                trace=trace,
                request_trace=request_trace,
            )

    def _execute_layered_locked(
        self,
        decision: DramaturgyDecision,
        *,
        anarchy_level: float,
        stack: bool,
        skip_interval_check: bool,
        stagger: bool,
        text_excerpt: str | None,
        trace: TraceContext | None = None,
        request_trace: RequestTrace | None = None,
    ) -> DirectorResult:
        req_trace = request_trace or begin_request_trace(trace)
        if self.safety.emergency_stop_active:
            emit_signal_trace_event(
                "director.execute_blocked",
                status="blocked",
                blocked_reason="emergency_stop_active",
                request_trace=req_trace,
            )
            return self._emergency_blocked_result(decision, "(inszenierung moment)")

        if stack and decision.visual:
            decision = decision.model_copy(deep=True)
            decision.visual = decision.visual.model_copy(
                update={"blend_mode": "layer"},
            )
        decision = apply_avatar_required_lights(decision, self.projectors)
        decision = _filter_decision_for_safety(decision, self.safety)
        decision = enrich_decision_metadata(decision)
        decision = _route_dramaturgy_from_avatar_projectors(decision, self.projectors)
        projector_blocked: str | None = None
        if decision.visual:
            allowed_proj, projector_blocked = self.projectors.can_play(decision.visual)
        else:
            allowed_proj = True
        allowed, blocked_reason = self.scheduler.can_execute(
            decision,
            anarchy_level=anarchy_level,
            skip_interval_check=skip_interval_check,
            dramaturgy_state=self.dramaturgy_state,
        )
        if not allowed_proj:
            allowed = False
            blocked_reason = projector_blocked
        elif (
            not allowed
            and blocked_reason == "light_cue_too_soon"
            and (decision.visual or decision.sound)
        ):
            # Hold the current look; still fire sound/video from this cue.
            decision = decision.model_copy(deep=True, update={"light": None})
            allowed, blocked_reason = self.scheduler.can_execute(
                decision,
                anarchy_level=anarchy_level,
                skip_interval_check=skip_interval_check,
                dramaturgy_state=self.dramaturgy_state,
            )

        dry_run = _effective_dry_run(self.safety)
        planned = build_osc_commands(decision, dry_run=dry_run)
        emit_signal_trace_event(
            "signal.planned",
            status="planned",
            planned_command_count=len(planned),
            request_trace=req_trace,
        )
        if planned:
            planned = attach_command_traces(planned, req_trace)
            self._emit_command_built_events(planned, req_trace)
        osc_commands: list[OscCommand] = []

        if not allowed:
            emit_signal_trace_event(
                "director.execute_blocked",
                status="blocked",
                blocked_reason=blocked_reason,
                request_trace=req_trace,
            )
        elif allowed and planned:
            osc_commands = self._dispatch_commands(planned, stagger=stagger)
            self.scheduler.mark_executed(decision)
            self.dramaturgy_state.apply_decision(decision, executed=True)
            if decision.visual:
                excerpt = text_excerpt
                if excerpt is None and decision.visual.video_type == "avatar":
                    last = self.state.last_event
                    if last and last.text and last.text != "(inszenierung moment)":
                        excerpt = last.text
                self.projectors.lock_after_play(
                    decision.visual,
                    text_excerpt=excerpt if decision.visual.video_type == "avatar" else None,
                )

        event = self.state.last_event or DialogueEvent(
            speaker=DialogueSpeaker.AI_A,
            text=text_excerpt or "(inszenierung moment)",
            topic="",
            mood=decision.mood,
            intensity=decision.intensity,
            tags=decision.tags,
            timestamp=decision.timestamp,
        )

        emit_dramaturgy_decision(
            decision,
            event=event,
            request_trace=req_trace,
            executed=allowed and bool(osc_commands),
            blocked_reason=blocked_reason,
            intensity_before=self.dramaturgy_state.scene_intensity,
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

    def accept_proposal(self, proposal_id: str, *, force: bool = False) -> DirectorResult | None:
        proposal = self.proposals.get(proposal_id)
        if proposal is None:
            return None
        from app.director.cues.cue_models import DecisionStatus

        self.proposals.set_status(proposal_id, DecisionStatus.SCHEDULED)
        return self.execute(proposal.decision, force=force)

    def reject_proposal(self, proposal_id: str) -> bool:
        from app.director.cues.cue_models import DecisionStatus

        updated = self.proposals.set_status(proposal_id, DecisionStatus.REJECTED)
        return updated is not None

    def override_proposal(
        self,
        proposal_id: str,
        decision: DramaturgyDecision,
        *,
        force: bool = True,
    ) -> DirectorResult | None:
        from app.director.cues.cue_models import DecisionStatus

        if self.proposals.get(proposal_id) is None:
            return None
        self.proposals.set_status(proposal_id, DecisionStatus.OVERRIDDEN)
        return self.execute(enrich_decision_metadata(decision), force=force)

    def process(self, event: DialogueEvent, *, force: bool = False) -> DirectorResult:
        if settings.director_execute_mode == "sequenced" and not force:
            return self.plan(event)
        planned_result = self.plan(event)
        if not force and planned_result.blocked_reason:
            return planned_result
        return self.execute(planned_result.decision, force=force)

    def _emergency_blocked_result(
        self,
        decision: DramaturgyDecision,
        text: str,
    ) -> DirectorResult:
        event = self.state.last_event or DialogueEvent(
            speaker=DialogueSpeaker.AI_A,
            text=text,
            topic="",
            mood=decision.mood,
            intensity=decision.intensity,
            tags=decision.tags,
            timestamp=decision.timestamp,
        )
        result = DirectorResult(
            event=event,
            decision=decision,
            executed=False,
            blocked_reason="emergency_stop_active",
            planned_commands=[],
            osc_commands=[],
        )
        self._store_result(result, log_executed=False)
        return result

    def _emit_command_built_events(
        self,
        commands: list[OscCommand],
        request_trace: RequestTrace,
    ) -> None:
        for cmd in commands:
            emit_signal_trace_event(
                "command.built",
                status="built",
                command=cmd,
                request_trace=request_trace,
            )

    def _dispatch_commands(self, commands: list[OscCommand], *, stagger: bool) -> list[OscCommand]:
        bridges = self._osc_bridges()
        if settings.director_osc_queue:
            return get_osc_command_queue().enqueue(
                commands,
                stagger=stagger,
                bridges=bridges,
                wait=False,
            )
        return self._execute_commands_sync(commands, stagger=stagger, bridges=bridges)

    def _osc_bridges(self) -> dict[str, object]:
        return {
            "touchdesigner": self.touchdesigner,
            "pixera": self.pixera,
            "sound": self.sound,
            "lighting": self.lighting,
        }

    def _execute_commands_sync(
        self,
        commands: list[OscCommand],
        *,
        stagger: bool,
        bridges: dict[str, object],
    ) -> list[OscCommand]:
        return send_osc_batch(commands, stagger=stagger, bridges=bridges)

    def _execute_commands(self, commands: list[OscCommand], *, stagger: bool) -> list[OscCommand]:
        """Backward-compatible alias used in tests."""
        return self._dispatch_commands(commands, stagger=stagger)

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

    def clear_for_performance(self) -> None:
        context = self.run_state.start_run()
        emit_signal_trace_event(
            "run.started",
            status="started",
            run_id=context.run_id,
            run_epoch=context.run_epoch,
            context_source="backend_authoritative",
        )
        self.safety.clear_emergency_stop()
        self.projectors.reconfigure_from_active_production()
        self.projectors.reset()
        self.projectors.allow_avatar_interrupt = True

    def emergency_stop(self) -> None:
        barrier = self.run_state.create_barrier("emergency_stop")
        emit_signal_trace_event(
            "run.barrier_created",
            status="barrier_created",
            run_id=barrier.run_id,
            run_epoch=barrier.run_epoch,
            barrier_id=barrier.barrier_id,
            barrier_reason=barrier.barrier_reason,
        )
        emit_signal_trace_event(
            "run.epoch_advanced",
            status="epoch_advanced",
            run_id=barrier.run_id,
            run_epoch=barrier.run_epoch,
            barrier_id=barrier.barrier_id,
            barrier_reason=barrier.barrier_reason,
        )
        from app.director.technik_hold import get_technik_hold_manager

        get_technik_hold_manager(self).stop()
        self.safety.emergency_stop()
        self.projectors.reset()
        self.scheduler.clear_active()
        dry_run = _effective_dry_run(self.safety)
        try:
            if not dry_run and settings.visual_output in ("pixera", "both"):
                from app.services.video_cue_catalog import get_video_cue_catalog_service

                catalog = get_video_cue_catalog_service().load()
                for projector in catalog.projectors:
                    self.pixera.apply_cue(f"{projector.pixera_prefix}.Black")
            if not dry_run and settings.visual_output in ("touchdesigner", "both"):
                self.touchdesigner.blackout()
            self.sound.stop_all(dry_run=dry_run)
            self.lighting.blackout(dry_run=dry_run)
        except Exception:
            _execute_logger.exception("legacy emergency outputs failed")
        try:
            from app.services.director_production_context import (
                emergency_stop_active_production_devices,
            )

            device_results = emergency_stop_active_production_devices()
            emit_signal_trace_event(
                "emergency.production_devices",
                status="stopped",
                detail={"devices": device_results},
            )
        except Exception:
            _execute_logger.exception("active production device emergency_stop failed")

    def refresh_output_targets(self) -> None:
        from app.director.output_targets import (
            effective_light_target,
            effective_video_target,
            effective_video_targets,
        )

        video_targets = effective_video_targets()
        video_host, video_port = effective_video_target()
        light_host, light_port = effective_light_target()
        self.pixera.reconfigure(hosts=video_targets)
        self.touchdesigner.reconfigure(video_host, video_port)
        self.lighting.reconfigure(light_host, light_port)


_pipeline: DirectorPipeline | None = None


def get_director_pipeline() -> DirectorPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = DirectorPipeline()
    return _pipeline
