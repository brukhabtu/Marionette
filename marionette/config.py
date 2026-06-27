"""Config loading and validation. YAML is the single source of truth; CLI flags
override individual fields."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path

import yaml

DEFAULT_CONFIG_PATH = Path("configs/default.yaml")


@dataclass(frozen=True)
class Config:
    dataset_name: str = "princeton-nlp/SWE-bench_Verified"
    split: str = "test"
    instance_ids_file: str | None = "configs/instances.txt"
    max_instances: int = 15

    orchestrator_model: str = "anthropic/claude-opus-4-8"
    orchestrator_prompt_version: str = "v1"
    orchestrator_schema_version: int = 1

    worker_models: tuple[str, ...] = ("anthropic/claude-haiku-4-5",)
    worker_temperature: float = 0.0
    step_limit: int = 50
    cost_limit: float = 1.0
    wall_time_limit_seconds: int = 0

    namespace: str | None = None
    arch: str = "arm64"
    cwd: str = "/testbed"

    cache_dir: str = ".cache/slices"
    out_dir: str = "runs"
    results_file: str = "runs/results.jsonl"

    grade_workers: int = 4

    dry_run: bool = False

    # Resolved pinned instance ids (loaded from instance_ids_file at load time).
    instance_ids: tuple[str, ...] = field(default_factory=tuple)

    def validate(self) -> Config:
        if not self.worker_models:
            raise ValueError("config.worker.models must be non-empty")
        if self.step_limit <= 0:
            raise ValueError("config.worker.step_limit must be > 0")
        if self.cost_limit <= 0:
            raise ValueError("config.worker.cost_limit must be > 0")
        if not self.orchestrator_model:
            raise ValueError("config.orchestrator.model_name is required")
        return self


def _read_pinned_ids(path: str | None) -> tuple[str, ...]:
    if not path:
        return ()
    p = Path(path)
    if not p.exists():
        return ()
    ids = []
    for line in p.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            ids.append(line)
    return tuple(ids)


def load_config(path: str | Path = DEFAULT_CONFIG_PATH, **overrides) -> Config:
    """Load YAML config, apply keyword overrides (CLI), resolve pinned ids, validate.

    Override keys match Config field names; None values are ignored so callers can
    pass through unset CLI options safely.
    """
    raw: dict = {}
    p = Path(path)
    if p.exists():
        raw = yaml.safe_load(p.read_text()) or {}

    orch = raw.get("orchestrator", {}) or {}
    worker = raw.get("worker", {}) or {}
    docker = raw.get("docker", {}) or {}
    paths = raw.get("paths", {}) or {}
    grading = raw.get("grading", {}) or {}

    cfg = Config(
        dataset_name=raw.get("dataset_name", Config.dataset_name),
        split=raw.get("split", Config.split),
        instance_ids_file=raw.get("instance_ids_file", Config.instance_ids_file),
        max_instances=int(raw.get("max_instances", Config.max_instances)),
        orchestrator_model=orch.get("model_name", Config.orchestrator_model),
        orchestrator_prompt_version=orch.get("prompt_version", Config.orchestrator_prompt_version),
        orchestrator_schema_version=int(orch.get("schema_version", Config.orchestrator_schema_version)),
        worker_models=tuple(worker.get("models", list(Config.worker_models))),
        worker_temperature=float(worker.get("temperature", Config.worker_temperature)),
        step_limit=int(worker.get("step_limit", Config.step_limit)),
        cost_limit=float(worker.get("cost_limit", Config.cost_limit)),
        wall_time_limit_seconds=int(worker.get("wall_time_limit_seconds", Config.wall_time_limit_seconds)),
        namespace=docker.get("namespace", Config.namespace),
        arch=docker.get("arch", Config.arch),
        cwd=docker.get("cwd", Config.cwd),
        cache_dir=paths.get("cache_dir", Config.cache_dir),
        out_dir=paths.get("out_dir", Config.out_dir),
        results_file=paths.get("results_file", Config.results_file),
        grade_workers=int(grading.get("grade_workers", Config.grade_workers)),
        dry_run=bool(raw.get("dry_run", Config.dry_run)),
    )

    clean_overrides = {k: v for k, v in overrides.items() if v is not None}
    if clean_overrides:
        cfg = replace(cfg, **clean_overrides)

    cfg = replace(cfg, instance_ids=_read_pinned_ids(cfg.instance_ids_file))
    return cfg.validate()
