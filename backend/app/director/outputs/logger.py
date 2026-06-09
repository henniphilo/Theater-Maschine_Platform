import json
from datetime import UTC, datetime
from pathlib import Path

import structlog

from app.core.config import settings
from app.director.cues.cue_models import DramaturgyDecision
from app.director.dialogue.models import DialogueEvent

logger = structlog.get_logger(__name__)


class DirectorLogger:
    def __init__(self, log_path: str | None = None) -> None:
        self.log_path = Path(log_path or settings.director_log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def log_event(
        self,
        event: DialogueEvent,
        decision: DramaturgyDecision,
        *,
        executed: bool,
        blocked_reason: str | None = None,
    ) -> None:
        entry = {
            "logged_at": datetime.now(UTC).isoformat(),
            "dialogue_event": event.model_dump(mode="json"),
            "decision": decision.model_dump(mode="json"),
            "executed": executed,
            "blocked_reason": blocked_reason,
        }
        line = json.dumps(entry, ensure_ascii=False)
        with self.log_path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
        logger.info("director_decision_logged", executed=executed, blocked_reason=blocked_reason)
