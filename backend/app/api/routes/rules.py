from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.rule import (
    LegacyRuleSummary,
    RuleCreate,
    RuleEvaluateRequest,
    RuleEvaluateResponse,
    RuleRead,
    RuleUpdate,
)
from app.services.rule_json_adapter import json_rules_to_canonical
from app.services.rule_service import (
    RuleNotFoundError,
    RuleService,
    RuleValidationError,
)

router = APIRouter(prefix="/rules", tags=["rules"])


def _service(db: Session = Depends(get_db)) -> RuleService:
    return RuleService(db)


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, RuleNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, RuleValidationError):
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    if isinstance(exc, ValidationError):
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    raise exc


@router.get("/legacy", response_model=list[LegacyRuleSummary])
def list_legacy_rules() -> list[LegacyRuleSummary]:
    """Read-only view of dramaturgy_rules.json compiled to CanonicalRule."""
    rows = json_rules_to_canonical()
    return [
        LegacyRuleSummary(
            id=r.id,
            name=r.name,
            enabled=r.enabled,
            priority=r.priority,
            conditions=[c.model_dump(exclude_none=True) for c in r.conditions],
            actions=[a.model_dump(exclude_none=True) for a in r.actions],
            cooldown_seconds=r.cooldown_seconds,
            source=r.source,
            meta=dict(r.meta),
        )
        for r in rows
    ]


@router.get("", response_model=list[RuleRead])
def list_rules(
    production_id: str | None = Query(default=None),
    enabled: bool | None = Query(default=None),
    service: RuleService = Depends(_service),
) -> list[RuleRead]:
    rows = service.list_rules(production_id=production_id, enabled=enabled)
    return [RuleRead.model_validate(row) for row in rows]


@router.post("", response_model=RuleRead, status_code=status.HTTP_201_CREATED)
def create_rule(
    payload: RuleCreate,
    service: RuleService = Depends(_service),
) -> RuleRead:
    try:
        row = service.create_rule(payload)
    except (RuleValidationError, ValidationError) as exc:
        raise _http_error(exc) from exc
    return RuleRead.model_validate(row)


@router.post("/evaluate", response_model=RuleEvaluateResponse)
def evaluate_rules_endpoint(
    production_id: str = Query(...),
    payload: RuleEvaluateRequest | None = None,
    service: RuleService = Depends(_service),
) -> RuleEvaluateResponse:
    body = payload or RuleEvaluateRequest()
    try:
        result = service.evaluate(production_id, body)
    except (RuleValidationError, ValidationError) as exc:
        raise _http_error(exc) from exc
    return RuleEvaluateResponse.model_validate(result)


@router.get("/{rule_id}", response_model=RuleRead)
def get_rule(
    rule_id: str,
    production_id: str | None = Query(default=None),
    service: RuleService = Depends(_service),
) -> RuleRead:
    try:
        row = service.get_rule(rule_id, production_id=production_id)
    except RuleNotFoundError as exc:
        raise _http_error(exc) from exc
    return RuleRead.model_validate(row)


@router.patch("/{rule_id}", response_model=RuleRead)
def update_rule(
    rule_id: str,
    payload: RuleUpdate,
    service: RuleService = Depends(_service),
) -> RuleRead:
    try:
        row = service.update_rule(rule_id, payload)
    except (RuleNotFoundError, RuleValidationError, ValidationError) as exc:
        raise _http_error(exc) from exc
    return RuleRead.model_validate(row)


@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_rule(
    rule_id: str,
    production_id: str | None = Query(default=None),
    service: RuleService = Depends(_service),
) -> Response:
    try:
        service.delete_rule(rule_id, production_id=production_id)
    except RuleNotFoundError as exc:
        raise _http_error(exc) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
