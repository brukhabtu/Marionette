"""Thin adapter over mini-swe-agent (pinned 2.4.2).

Every use of mini-swe-agent's classes/attributes is funneled through here, so an
upgrade that renames something is a one-file fix. Verified against 2.4.2:
- agent.run(task, **vars) -> {"exit_status", "submission"}
- agent.cost (float), agent.n_calls (int) accumulate on the AGENT
- each assistant message carries extra.response (full litellm dump incl. usage)
  and extra.cost
"""

from __future__ import annotations

from typing import Any

from .types import AgentRunResult


def make_worker_model(model_name: str, temperature: float = 0.0) -> Any:
    """Construct a litellm-backed worker model at the given temperature."""
    from minisweagent.models.litellm_model import LitellmModel

    return LitellmModel(model_name=model_name, model_kwargs={"temperature": temperature})


def make_docker_env(image: str, *, cwd: str = "/testbed", env: dict | None = None) -> Any:
    """Construct a DockerEnvironment bound to a SWE-bench instance image.

    Hold the returned object for the whole instance (all slices) — its __del__
    tears down the container, so letting it GC between slices loses the working tree.
    """
    from minisweagent.environments.docker import DockerEnvironment

    return DockerEnvironment(image=image, cwd=cwd, env=env or {})


def close_env(env: Any) -> None:
    """Explicitly tear down an environment if it supports cleanup."""
    cleanup = getattr(env, "cleanup", None)
    if callable(cleanup):
        try:
            cleanup()
        except Exception:  # noqa: BLE001 - best-effort teardown
            pass


def run_agent_once(
    model: Any,
    env: Any,
    *,
    system_template: str,
    instance_template: str,
    step_limit: int,
    cost_limit: float,
    wall_time_limit_seconds: int = 0,
    output_path: str | None = None,
) -> AgentRunResult:
    """Run a single fresh agent against an existing env. Conversation resets here;
    any file edits already on disk in `env` persist."""
    from minisweagent.agents.default import DefaultAgent

    agent = DefaultAgent(
        model,
        env,
        system_template=system_template,
        instance_template=instance_template,
        step_limit=step_limit,
        cost_limit=cost_limit,
        wall_time_limit_seconds=wall_time_limit_seconds,
        output_path=output_path,
    )
    info = agent.run(task="")
    return AgentRunResult(
        exit_status=str(info.get("exit_status", "")),
        submission=str(info.get("submission", "")),
        n_calls=int(getattr(agent, "n_calls", 0)),
        cost=float(getattr(agent, "cost", 0.0)),
        messages=list(getattr(agent, "messages", [])),
    )


def git_diff(env: Any) -> str:
    """Cumulative diff vs the repo's committed base, as model_patch.

    Runs in the environment's own working directory (set when the env is built:
    /testbed for Docker, the temp repo for the mock). Matches the standard
    SWE-bench extraction: stage everything, then diff the index (captures edits and
    any new source files). The grader applies this patch to a clean container and
    then the gold test patch on top, so worker edits to tests don't survive grading.
    """
    cmd = "git -c core.fileMode=false add -A && git diff --cached --no-color"
    result = env.execute({"command": cmd})
    return result.get("output", "")
