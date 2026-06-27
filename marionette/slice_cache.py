"""On-disk cache of orchestrator slice plans.

The cache key binds a plan to the instance, the orchestrator model, the exact
orchestrator prompt text, and a schema version. Changing any of these produces a
new key, so stale plans are never reused.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .config import Config
from .prompts import ORCHESTRATOR_PROMPT
from .types import SlicePlan


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def cache_key(instance_id: str, orchestrator_model: str, prompt_text: str, schema_version: int) -> str:
    raw = f"{instance_id}|{orchestrator_model}|{_sha(prompt_text)}|{schema_version}"
    return _sha(raw)[:16]


def key_for(cfg: Config, instance_id: str) -> str:
    return cache_key(
        instance_id,
        cfg.orchestrator_model,
        ORCHESTRATOR_PROMPT,
        cfg.orchestrator_schema_version,
    )


def path_for(cfg: Config, instance_id: str, key: str) -> Path:
    return Path(cfg.cache_dir) / f"{instance_id}.{key}.json"


def load(cfg: Config, instance_id: str) -> SlicePlan | None:
    key = key_for(cfg, instance_id)
    p = path_for(cfg, instance_id, key)
    if not p.exists():
        return None
    plan = SlicePlan.from_dict(json.loads(p.read_text()))
    # Defensive: ignore a file whose embedded key disagrees with the path.
    return plan if plan.cache_key == key else None


def save(cfg: Config, plan: SlicePlan) -> Path:
    p = path_for(cfg, plan.instance_id, plan.cache_key)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(plan.to_dict(), indent=2))
    return p
