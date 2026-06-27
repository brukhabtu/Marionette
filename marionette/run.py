"""Marionette CLI: discover | decompose | run | plot."""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path

import typer

from . import dataset, grading, orchestrator, results
from .config import Config, load_config
from .types import ResultRow, SlicePlan
from .worker import EnvFactory, ModelFactory, run_worker_on_instance

app = typer.Typer(add_completion=False, help="Worker-on-slices cost/accuracy harness.")

# A GradeFn maps (worker_model, {instance_id: patch}) -> {instance_id: resolved}.
GradeFn = Callable[[str, dict[str, str]], dict[str, bool]]


# --------------------------------------------------------------------------- #
# Component wiring (real vs dry-run)
# --------------------------------------------------------------------------- #
def _real_env_factory(cfg: Config) -> EnvFactory:
    from . import images, msa_adapter

    def factory(instance: dict):
        image = images.instance_image_key(instance, namespace=cfg.namespace, arch=cfg.arch)
        return msa_adapter.make_docker_env(image, cwd=cfg.cwd)

    return factory


def _real_grade_fn(cfg: Config) -> GradeFn:
    def grade_fn(worker_model: str, patches: dict[str, str]) -> dict[str, bool]:
        slug = grading.model_slug(worker_model)
        run_id = f"marionette-{slug}-{time.strftime('%Y%m%d-%H%M%S')}"
        preds_path = Path(cfg.out_dir) / "predictions" / f"{slug}.{run_id}.jsonl"
        return grading.grade(cfg, worker_model, patches, run_id, preds_path)

    return grade_fn


def _dry_run_components(cfg: Config):
    """Return (complete_fn, env_factory, model_factory, grade_fn) for a dry-run."""
    from .mock.environment import make_mock_env_factory
    from .mock.model import make_mock_model_factory, mock_orchestrator_complete

    complete_fn = mock_orchestrator_complete()
    env_factory = make_mock_env_factory()
    model_factory = make_mock_model_factory()

    def grade_fn(worker_model: str, patches: dict[str, str]) -> dict[str, bool]:
        # Resolved iff the worker produced a non-empty cumulative diff.
        return {iid: bool(patch.strip()) for iid, patch in patches.items()}

    return complete_fn, env_factory, model_factory, grade_fn


# --------------------------------------------------------------------------- #
# Core sweep (pure-ish; injected components make it testable)
# --------------------------------------------------------------------------- #
def execute_sweep(
    cfg: Config,
    instances: list[dict],
    *,
    env_factory: EnvFactory,
    grade_fn: GradeFn,
    complete_fn=None,
    model_factory: ModelFactory | None = None,
    use_cache: bool = True,
) -> list[ResultRow]:
    plans: dict[str, SlicePlan] = {}
    for inst in instances:
        plans[inst["instance_id"]] = orchestrator.decompose(
            inst, cfg, complete_fn=complete_fn, use_cache=use_cache
        )

    all_rows: list[ResultRow] = []
    for worker_model in cfg.worker_models:
        outcomes = {}
        patches: dict[str, str] = {}
        for inst in instances:
            iid = inst["instance_id"]
            outcome = run_worker_on_instance(
                inst, plans[iid], worker_model, cfg, env_factory, model_factory
            )
            outcomes[iid] = outcome
            patches[iid] = outcome.model_patch

        resolved_map = grade_fn(worker_model, patches)

        rows = []
        for inst in instances:
            iid = inst["instance_id"]
            plan = plans[iid]
            rows.append(
                results.build_row(
                    worker_model,
                    iid,
                    plan.orchestrator_tokens,
                    plan.orchestrator_cost_usd,
                    outcomes[iid],
                    resolved_map.get(iid, False),
                )
            )
        results.append_rows(cfg.results_file, rows)
        all_rows.extend(rows)
    return all_rows


# --------------------------------------------------------------------------- #
# Commands
# --------------------------------------------------------------------------- #
@app.command()
def discover(config: str = "configs/default.yaml", max_instances: int | None = None):
    """List candidate multi-file/multi-hunk Verified instance IDs."""
    cfg = load_config(config, max_instances=max_instances)
    candidates = dataset.discover(cfg)
    for inst in candidates:
        files, hunks = dataset.count_files_hunks(inst.get("patch", ""))
        typer.echo(f"{inst['instance_id']}\tfiles={files}\thunks={hunks}")
    typer.echo(f"# {len(candidates)} candidates", err=True)


@app.command()
def decompose(
    config: str = "configs/default.yaml",
    instance: str | None = typer.Option(None, help="Single instance_id; default = full set"),
):
    """Build and cache slice plans (orchestrator only; no Docker)."""
    cfg = load_config(config)
    instances = dataset.select(cfg)
    if instance:
        instances = [i for i in instances if i["instance_id"] == instance]
        if not instances:
            raise typer.BadParameter(f"instance {instance} not in selected set")
    for inst in instances:
        plan = orchestrator.decompose(inst, cfg)
        typer.echo(
            f"{plan.instance_id}: {len(plan.slices)} slices, "
            f"{plan.orchestrator_tokens} tokens, ${plan.orchestrator_cost_usd:.4f}"
        )


@app.command()
def run(
    config: str = "configs/default.yaml",
    dry_run: bool = typer.Option(False, "--dry-run", help="No Docker/LLM/SWE-bench; mock everything"),
    worker: list[str] | None = typer.Option(None, help="Override worker model(s)"),
    instance: list[str] | None = typer.Option(None, help="Restrict to instance_id(s)"),
):
    """Run the sweep: decompose -> worker per slice -> grade -> results rows."""
    overrides = {}
    if worker:
        overrides["worker_models"] = tuple(worker)
    cfg = load_config(config, **overrides)

    if dry_run:
        from .mock.fixtures import MOCK_INSTANCE

        instances = [MOCK_INSTANCE]
        complete_fn, env_factory, model_factory, grade_fn = _dry_run_components(cfg)
        rows = execute_sweep(
            cfg,
            instances,
            env_factory=env_factory,
            grade_fn=grade_fn,
            complete_fn=complete_fn,
            model_factory=model_factory,
            use_cache=False,
        )
    else:
        instances = dataset.select(cfg)
        if instance:
            wanted = set(instance)
            instances = [i for i in instances if i["instance_id"] in wanted]
        rows = execute_sweep(
            cfg,
            instances,
            env_factory=_real_env_factory(cfg),
            grade_fn=_real_grade_fn(cfg),
        )

    resolved = sum(1 for r in rows if r.resolved)
    typer.echo(f"Wrote {len(rows)} rows to {cfg.results_file} ({resolved} resolved)")


@app.command()
def plot(
    config: str = "configs/default.yaml",
    out: str | None = typer.Option(None, help="Output PNG path"),
):
    """Plot resolve-rate vs cost (one point per worker model)."""
    from .plot import plot as make_plot

    cfg = load_config(config)
    out_path = out or str(Path(cfg.out_dir) / "frontier.png")
    written = make_plot(cfg.results_file, out_path)
    typer.echo(f"Wrote {written}")


if __name__ == "__main__":
    app()
