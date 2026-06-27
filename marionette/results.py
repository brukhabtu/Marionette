"""Assemble ResultRows and persist them as JSONL.

Status precedence (one centralized, tested rule):
  error      -> the worker raised before producing a gradeable diff
  resolved   -> grading reports resolved == True
  hit_limit  -> a slice hit the step/cost cap and the result is not resolved
  wrong      -> completed and graded, but not resolved
"""

from __future__ import annotations

import json
from pathlib import Path

from .types import STATUS_ERROR, STATUS_HIT_LIMIT, STATUS_RESOLVED, STATUS_WRONG, ResultRow, WorkerOutcome


def decide_status(*, error: bool, resolved: bool, hit_limit: bool) -> str:
    if error:
        return STATUS_ERROR
    if resolved:
        return STATUS_RESOLVED
    if hit_limit:
        return STATUS_HIT_LIMIT
    return STATUS_WRONG


def build_row(
    worker_model: str,
    instance_id: str,
    plan_orchestrator_tokens: int,
    plan_orchestrator_cost: float,
    outcome: WorkerOutcome,
    resolved: bool,
) -> ResultRow:
    status = decide_status(
        error=outcome.error is not None,
        resolved=resolved,
        hit_limit=outcome.hit_limit,
    )
    return ResultRow(
        worker_model=worker_model,
        instance_id=instance_id,
        resolved=bool(resolved),
        status=status,
        worker_iterations=outcome.iterations,
        orchestrator_tokens=plan_orchestrator_tokens,
        worker_tokens=outcome.worker_acct.tokens,
        cost_usd=round(plan_orchestrator_cost + outcome.worker_acct.cost_usd, 6),
    )


def append_rows(path: str | Path, rows: list[ResultRow]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a") as f:
        for r in rows:
            f.write(json.dumps(r.to_dict()) + "\n")


def read_rows(path: str | Path) -> list[ResultRow]:
    p = Path(path)
    if not p.exists():
        return []
    rows = []
    for line in p.read_text().splitlines():
        line = line.strip()
        if line:
            rows.append(ResultRow.from_dict(json.loads(line)))
    return rows
