"""SWE-bench Verified dataset loading and multi-file/multi-hunk filtering."""

from __future__ import annotations

import re

from .config import Config

# A gold patch must touch at least this many files OR contain at least this many
# hunks to be considered "decomposable" (single-concern fixes don't exercise the
# slice plan).
MIN_FILES = 2
MIN_HUNKS = 2

_HUNK_RE = re.compile(r"^@@ ", re.MULTILINE)


def count_files_hunks(patch: str) -> tuple[int, int]:
    """Count changed files and hunks in a unified diff string."""
    if not patch:
        return 0, 0
    files = patch.count("diff --git ")
    hunks = len(_HUNK_RE.findall(patch))
    return files, hunks


def is_multi(patch: str) -> bool:
    files, hunks = count_files_hunks(patch)
    return files >= MIN_FILES or hunks >= MIN_HUNKS


def load_verified(cfg: Config) -> list[dict]:
    """Load the full Verified split as a list of plain dicts."""
    from datasets import load_dataset

    ds = load_dataset(cfg.dataset_name, split=cfg.split)
    return [dict(row) for row in ds]


def discover(cfg: Config) -> list[dict]:
    """Candidate instances: multi-file/multi-hunk gold patches, capped at max_instances."""
    rows = load_verified(cfg)
    multi = [r for r in rows if is_multi(r.get("patch", ""))]
    return multi[: cfg.max_instances]


def select(cfg: Config) -> list[dict]:
    """Resolve the instance set for a run.

    Pinned IDs (from instance_ids_file) win and are returned verbatim. Otherwise
    fall back to the auto-filtered candidates from `discover`.
    """
    if cfg.instance_ids:
        wanted = set(cfg.instance_ids)
        rows = load_verified(cfg)
        by_id = {r["instance_id"]: r for r in rows if r["instance_id"] in wanted}
        missing = wanted - set(by_id)
        if missing:
            raise ValueError(f"Pinned instance_ids not found in dataset: {sorted(missing)}")
        # Preserve the pinned order.
        return [by_id[iid] for iid in cfg.instance_ids]
    return discover(cfg)
