"""Plot the cost/accuracy frontier: one point per worker model."""

from __future__ import annotations

from pathlib import Path

from .results import read_rows
from .types import ResultRow


def aggregate(rows: list[ResultRow]) -> dict[str, dict[str, float]]:
    """Per worker model: resolve_rate, mean cost/instance, n instances."""
    by_model: dict[str, list[ResultRow]] = {}
    for r in rows:
        by_model.setdefault(r.worker_model, []).append(r)

    out: dict[str, dict[str, float]] = {}
    for model, rs in by_model.items():
        n = len(rs)
        resolved = sum(1 for r in rs if r.resolved)
        total_cost = sum(r.cost_usd for r in rs)
        out[model] = {
            "n": n,
            "resolve_rate": resolved / n if n else 0.0,
            "mean_cost_usd": total_cost / n if n else 0.0,
        }
    return out


def plot(results_file: str | Path, out_path: str | Path) -> Path:
    rows = read_rows(results_file)
    if not rows:
        raise ValueError(f"no results in {results_file}")
    agg = aggregate(rows)

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(7, 5))
    for model, m in agg.items():
        ax.scatter(m["mean_cost_usd"], m["resolve_rate"], s=80)
        ax.annotate(
            model.split("/")[-1],
            (m["mean_cost_usd"], m["resolve_rate"]),
            textcoords="offset points",
            xytext=(6, 4),
            fontsize=9,
        )
    ax.set_xlabel("Mean cost per instance (USD)")
    ax.set_ylabel("Resolve rate")
    ax.set_title("Worker-on-slices: cost vs accuracy frontier")
    ax.set_ylim(-0.02, 1.02)
    ax.grid(True, alpha=0.3)

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(out, dpi=120)
    plt.close(fig)
    return out
