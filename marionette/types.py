"""Core data types for the harness.

`ResultRow` matches the spec schema exactly (one row per (worker_model, instance_id)).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

# Allowed values for ResultRow.status.
STATUS_RESOLVED = "resolved"
STATUS_WRONG = "wrong"
STATUS_HIT_LIMIT = "hit_limit"
STATUS_ERROR = "error"
STATUSES = (STATUS_RESOLVED, STATUS_WRONG, STATUS_HIT_LIMIT, STATUS_ERROR)


@dataclass(frozen=True)
class Slice:
    """A single scoped unit of work the worker tackles in one agent run."""

    scope: str
    target_files: list[str]

    def to_dict(self) -> dict:
        return {"scope": self.scope, "target_files": list(self.target_files)}

    @staticmethod
    def from_dict(d: dict) -> Slice:
        return Slice(scope=d["scope"], target_files=list(d.get("target_files", [])))


@dataclass(frozen=True)
class SlicePlan:
    """The orchestrator's decomposition for one instance. Cached and reused across
    every worker run, so orchestrator_tokens/cost are a per-instance constant."""

    instance_id: str
    slices: list[Slice]
    orchestrator_model: str
    orchestrator_tokens: int
    orchestrator_cost_usd: float
    cache_key: str

    def to_dict(self) -> dict:
        return {
            "instance_id": self.instance_id,
            "slices": [s.to_dict() for s in self.slices],
            "orchestrator_model": self.orchestrator_model,
            "orchestrator_tokens": self.orchestrator_tokens,
            "orchestrator_cost_usd": self.orchestrator_cost_usd,
            "cache_key": self.cache_key,
        }

    @staticmethod
    def from_dict(d: dict) -> SlicePlan:
        return SlicePlan(
            instance_id=d["instance_id"],
            slices=[Slice.from_dict(s) for s in d["slices"]],
            orchestrator_model=d["orchestrator_model"],
            orchestrator_tokens=int(d["orchestrator_tokens"]),
            orchestrator_cost_usd=float(d["orchestrator_cost_usd"]),
            cache_key=d["cache_key"],
        )


@dataclass
class RoleAccounting:
    """Token/cost tally for a single role (orchestrator or worker)."""

    tokens: int = 0
    cost_usd: float = 0.0
    n_calls: int = 0


@dataclass
class ResultRow:
    """One row per (worker_model, instance_id). Field set/types match the spec."""

    worker_model: str
    instance_id: str
    resolved: bool
    status: str  # resolved | wrong | hit_limit | error
    worker_iterations: int
    orchestrator_tokens: int
    worker_tokens: int
    cost_usd: float

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> ResultRow:
        return ResultRow(
            worker_model=d["worker_model"],
            instance_id=d["instance_id"],
            resolved=bool(d["resolved"]),
            status=d["status"],
            worker_iterations=int(d["worker_iterations"]),
            orchestrator_tokens=int(d["orchestrator_tokens"]),
            worker_tokens=int(d["worker_tokens"]),
            cost_usd=float(d["cost_usd"]),
        )


@dataclass
class AgentRunResult:
    """Normalized result of a single agent.run() (returned by the msa adapter)."""

    exit_status: str
    submission: str
    n_calls: int
    cost: float
    messages: list[dict] = field(default_factory=list)


@dataclass
class WorkerOutcome:
    """Result of running the worker across all slices for one instance."""

    model_patch: str
    iterations: int
    worker_acct: RoleAccounting
    hit_limit: bool
    error: str | None = None
