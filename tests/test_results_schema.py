from marionette.results import append_rows, build_row, decide_status, read_rows
from marionette.types import (
    STATUS_ERROR,
    STATUS_HIT_LIMIT,
    STATUS_RESOLVED,
    STATUS_WRONG,
    RoleAccounting,
    WorkerOutcome,
)

SPEC_FIELDS = {
    "worker_model",
    "instance_id",
    "resolved",
    "status",
    "worker_iterations",
    "orchestrator_tokens",
    "worker_tokens",
    "cost_usd",
}


def _outcome(error=None, hit_limit=False, tokens=200, cost=0.02, iters=4):
    acct = RoleAccounting(tokens=tokens, cost_usd=cost, n_calls=iters)
    return WorkerOutcome(
        model_patch="diff", iterations=iters, worker_acct=acct, hit_limit=hit_limit, error=error
    )


def test_status_precedence():
    assert decide_status(error=True, resolved=True, hit_limit=True) == STATUS_ERROR
    assert decide_status(error=False, resolved=True, hit_limit=True) == STATUS_RESOLVED
    assert decide_status(error=False, resolved=False, hit_limit=True) == STATUS_HIT_LIMIT
    assert decide_status(error=False, resolved=False, hit_limit=False) == STATUS_WRONG


def test_build_row_schema_and_cost_sum():
    row = build_row("anthropic/claude-haiku-4-5", "inst-1", 5000, 0.05, _outcome(), resolved=True)
    assert set(row.to_dict().keys()) == SPEC_FIELDS
    assert row.orchestrator_tokens == 5000
    assert row.worker_tokens == 200
    assert row.cost_usd == round(0.05 + 0.02, 6)
    assert row.status == STATUS_RESOLVED
    assert row.resolved is True


def test_hit_limit_not_resolved():
    row = build_row("m", "i", 0, 0.0, _outcome(hit_limit=True), resolved=False)
    assert row.status == STATUS_HIT_LIMIT


def test_error_row():
    row = build_row("m", "i", 0, 0.0, _outcome(error="Boom: bad"), resolved=False)
    assert row.status == STATUS_ERROR


def test_jsonl_roundtrip(tmp_path):
    path = tmp_path / "results.jsonl"
    row = build_row("m", "i", 10, 0.01, _outcome(), resolved=False)
    append_rows(path, [row])
    back = read_rows(path)
    assert len(back) == 1
    assert back[0].to_dict() == row.to_dict()
