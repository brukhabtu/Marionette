"""End-to-end dry-run: mock model + real temp-git LocalEnvironment, real agent loop."""

from marionette.config import Config
from marionette.mock.environment import make_mock_env_factory
from marionette.mock.fixtures import MOCK_INSTANCE, MOCK_SLICES_JSON
from marionette.mock.model import make_mock_model_factory, mock_orchestrator_complete
from marionette.run import execute_sweep
from marionette.types import STATUS_RESOLVED


def _cfg(tmp_path) -> Config:
    return Config(
        instance_ids_file=None,
        worker_models=("mock/haiku",),
        cache_dir=str(tmp_path / "cache"),
        out_dir=str(tmp_path / "runs"),
        results_file=str(tmp_path / "runs/results.jsonl"),
        step_limit=10,
        cost_limit=5.0,
    )


def test_decompose_mock_produces_two_slices(tmp_path):
    from marionette import orchestrator

    cfg = _cfg(tmp_path)
    plan = orchestrator.decompose(
        MOCK_INSTANCE, cfg, complete_fn=mock_orchestrator_complete(MOCK_SLICES_JSON), use_cache=False
    )
    assert len(plan.slices) == 2
    assert plan.orchestrator_tokens == 580  # 500 + 80 from the mock complete_fn


def test_full_dry_run_sweep(tmp_path):
    cfg = _cfg(tmp_path)

    def grade_fn(worker_model, patches):
        # Resolve iff a non-empty diff was produced.
        return {iid: bool(p.strip()) for iid, p in patches.items()}

    rows = execute_sweep(
        cfg,
        [MOCK_INSTANCE],
        env_factory=make_mock_env_factory(),
        grade_fn=grade_fn,
        complete_fn=mock_orchestrator_complete(),
        model_factory=make_mock_model_factory(),
        use_cache=False,
    )

    assert len(rows) == 1
    row = rows[0]
    assert row.instance_id == MOCK_INSTANCE["instance_id"]
    assert row.resolved is True
    assert row.status == STATUS_RESOLVED
    # Two slices, each: 1 edit call + 1 submit call => >= 2 iterations.
    assert row.worker_iterations >= 2
    assert row.worker_tokens > 0
    assert row.orchestrator_tokens == 580
    assert row.cost_usd > 0
    # Results were persisted.
    from marionette.results import read_rows

    assert len(read_rows(cfg.results_file)) == 1
