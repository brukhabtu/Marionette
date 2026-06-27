"""Grading via the SWE-bench harness.

The worker container only produces a diff. Grading is a SEPARATE pass:
run_evaluation applies model_patch to a fresh clean instance container and runs
FAIL_TO_PASS + PASS_TO_PASS itself. We invoke it once per worker model (one
predictions file, one run_id) and read the per-instance report.json it writes.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from .config import Config

EVAL_LOG_ROOT = Path("logs/run_evaluation")


def model_slug(worker_model: str) -> str:
    return worker_model.replace("/", "__")


def write_predictions(path: str | Path, worker_model: str, patches_by_instance: dict[str, str]) -> Path:
    """Write a SWE-bench predictions JSONL (one line per instance)."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w") as f:
        for instance_id, patch in patches_by_instance.items():
            f.write(
                json.dumps(
                    {
                        "instance_id": instance_id,
                        "model_name_or_path": worker_model,
                        "model_patch": patch or "",
                    }
                )
                + "\n"
            )
    return p


def build_eval_command(
    cfg: Config, preds_path: str | Path, run_id: str, instance_ids: list[str]
) -> list[str]:
    ns = "none" if cfg.namespace is None else cfg.namespace
    return [
        sys.executable,
        "-m",
        "swebench.harness.run_evaluation",
        "--dataset_name",
        cfg.dataset_name,
        "--split",
        cfg.split,
        "--predictions_path",
        str(preds_path),
        "--run_id",
        run_id,
        "--namespace",
        ns,
        "--instance_ids",
        *instance_ids,
        "--max_workers",
        str(cfg.grade_workers),
        "--cache_level",
        "env",
    ]


def parse_reports(run_id: str, worker_model: str, instance_ids: list[str]) -> dict[str, bool]:
    """Read each instance's report.json -> {instance_id: resolved}."""
    base = EVAL_LOG_ROOT / run_id / model_slug(worker_model)
    out: dict[str, bool] = {}
    for iid in instance_ids:
        rp = base / iid / "report.json"
        if not rp.exists():
            out[iid] = False
            continue
        try:
            report = json.loads(rp.read_text())
            out[iid] = bool(report.get(iid, {}).get("resolved", False))
        except Exception:  # noqa: BLE001 - missing/garbled report grades as unresolved
            out[iid] = False
    return out


def grade(
    cfg: Config,
    worker_model: str,
    patches_by_instance: dict[str, str],
    run_id: str,
    preds_path: str | Path,
) -> dict[str, bool]:
    """Run grading for one worker model and return {instance_id: resolved}."""
    instance_ids = list(patches_by_instance.keys())
    write_predictions(preds_path, worker_model, patches_by_instance)
    cmd = build_eval_command(cfg, preds_path, run_id, instance_ids)
    subprocess.run(cmd, check=False)
    return parse_reports(run_id, worker_model, instance_ids)
