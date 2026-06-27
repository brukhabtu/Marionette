"""Worker runner: one fresh agent per slice, sharing a single environment.

Conversation resets every slice; file edits accumulate on disk between slices. The
model_patch is the cumulative git diff after the last slice.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from . import msa_adapter
from .accounting import accumulate
from .config import Config
from .prompts import render_worker_templates
from .types import RoleAccounting, SlicePlan, WorkerOutcome

# An EnvFactory builds a fresh environment for an instance (Docker for real runs, a
# local temp-git env for dry-run). A ModelFactory builds a worker model per slice.
EnvFactory = Callable[[dict], Any]
ModelFactory = Callable[[str, float], Any]

# Exit statuses that mean the worker ran out of budget rather than finishing.
LIMIT_EXITS = {"LimitsExceeded", "TimeExceeded"}


def _traj_path(cfg: Config, worker_model: str, instance_id: str, slice_idx: int) -> str | None:
    if not cfg.out_dir:
        return None
    slug = worker_model.replace("/", "__")
    p = Path(cfg.out_dir) / "trajectories" / slug / instance_id
    p.mkdir(parents=True, exist_ok=True)
    return str(p / f"slice_{slice_idx}.json")


def run_worker_on_instance(
    instance: dict,
    plan: SlicePlan,
    worker_model_name: str,
    cfg: Config,
    env_factory: EnvFactory,
    model_factory: ModelFactory | None = None,
) -> WorkerOutcome:
    """Run all slices for one instance and return the cumulative diff + accounting."""
    instance_id = instance["instance_id"]
    issue_text = instance.get("problem_statement", "") or ""
    make_model = model_factory or msa_adapter.make_worker_model

    worker_acct = RoleAccounting()
    total_iters = 0
    hit_limit = False
    env: Any = None
    try:
        env = env_factory(instance)
        for i, sl in enumerate(plan.slices):
            model = make_model(worker_model_name, cfg.worker_temperature)
            system_t, instance_t = render_worker_templates(issue_text, sl, i, len(plan.slices))
            res = msa_adapter.run_agent_once(
                model,
                env,
                system_template=system_t,
                instance_template=instance_t,
                step_limit=cfg.step_limit,
                cost_limit=cfg.cost_limit,
                wall_time_limit_seconds=cfg.wall_time_limit_seconds,
                output_path=_traj_path(cfg, worker_model_name, instance_id, i),
            )
            total_iters += res.n_calls
            accumulate(worker_acct, res)
            if res.exit_status in LIMIT_EXITS:
                hit_limit = True
            # Conversation resets next slice; disk edits in `env` persist.

        model_patch = msa_adapter.git_diff(env)
        return WorkerOutcome(
            model_patch=model_patch,
            iterations=total_iters,
            worker_acct=worker_acct,
            hit_limit=hit_limit,
            error=None,
        )
    except Exception as e:  # noqa: BLE001 - any failure becomes an `error` row
        return WorkerOutcome(
            model_patch="",
            iterations=total_iters,
            worker_acct=worker_acct,
            hit_limit=hit_limit,
            error=f"{type(e).__name__}: {e}",
        )
    finally:
        if env is not None:
            msa_adapter.close_env(env)
