"""In-memory cue proposal lifecycle for operator review."""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import RLock

from app.director.cues.cue_models import CueProposal, DecisionStatus, DramaturgyDecision
from app.director.dramaturgy.reason_short import enrich_decision_metadata


@dataclass
class ProposalStore:
    _proposals: dict[str, CueProposal] = field(default_factory=dict)
    _lock: RLock = field(default_factory=RLock)

    def create(self, decision: DramaturgyDecision, *, text_snippet: str = "") -> CueProposal:
        enriched = enrich_decision_metadata(decision.model_copy(deep=True))
        proposal = CueProposal(
            proposal_id=f"proposal-{secrets.token_hex(4)}",
            decision=enriched,
            status=DecisionStatus.SUGGESTED,
            reason_short=enriched.reason_short,
            dramaturgical_function=enriched.dramaturgical_function,
            text_snippet=text_snippet[:200],
            created_at=datetime.now(UTC),
        )
        with self._lock:
            self._proposals[proposal.proposal_id] = proposal
            if len(self._proposals) > 100:
                oldest = sorted(self._proposals.values(), key=lambda p: p.created_at)[:20]
                for item in oldest:
                    self._proposals.pop(item.proposal_id, None)
        return proposal

    def get(self, proposal_id: str) -> CueProposal | None:
        with self._lock:
            return self._proposals.get(proposal_id)

    def list_open(self) -> list[CueProposal]:
        with self._lock:
            return [
                p
                for p in self._proposals.values()
                if p.status in {DecisionStatus.SUGGESTED, DecisionStatus.SCHEDULED}
            ]

    def set_status(self, proposal_id: str, status: DecisionStatus) -> CueProposal | None:
        with self._lock:
            proposal = self._proposals.get(proposal_id)
            if proposal is None:
                return None
            updated = proposal.model_copy(update={"status": status})
            self._proposals[proposal_id] = updated
            return updated
