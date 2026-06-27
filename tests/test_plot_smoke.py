from marionette.plot import aggregate, plot
from marionette.results import append_rows
from marionette.types import ResultRow


def _row(model, instance, resolved, cost):
    return ResultRow(
        worker_model=model,
        instance_id=instance,
        resolved=resolved,
        status="resolved" if resolved else "wrong",
        worker_iterations=3,
        orchestrator_tokens=500,
        worker_tokens=200,
        cost_usd=cost,
    )


def test_aggregate_resolve_rate_and_cost():
    rows = [
        _row("m1", "a", True, 0.10),
        _row("m1", "b", False, 0.20),
        _row("m2", "a", True, 0.50),
    ]
    agg = aggregate(rows)
    assert agg["m1"]["resolve_rate"] == 0.5
    assert round(agg["m1"]["mean_cost_usd"], 3) == 0.15
    assert agg["m2"]["resolve_rate"] == 1.0


def test_plot_writes_png(tmp_path):
    results_file = tmp_path / "results.jsonl"
    append_rows(results_file, [_row("m1", "a", True, 0.1), _row("m2", "a", False, 0.2)])
    out = plot(results_file, tmp_path / "frontier.png")
    assert out.exists()
    assert out.stat().st_size > 0
