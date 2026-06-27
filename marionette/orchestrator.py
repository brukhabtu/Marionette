"""Decomposition step: a fixed large model turns issue text into a slice plan.

Uses litellm.completion DIRECTLY (no agent / no environment) because the input is
issue text only. The result is cached per instance and reused for every worker run,
so orchestrator tokens/cost are a per-instance constant.
"""

from __future__ import annotations

from collections.abc import Callable

from . import slice_cache
from .config import Config
from .prompts import render_orchestrator_messages, slices_from_json
from .types import SlicePlan

MAX_PARSE_RETRIES = 2

# A CompleteFn takes (model_name, messages, temperature) and returns
# (text, prompt_tokens, completion_tokens, cost_usd). Injected for tests/dry-run.
CompleteFn = Callable[[str, list[dict], float], tuple[str, int, int, float]]


def _litellm_complete(model_name: str, messages: list[dict], temperature: float):
    import litellm

    resp = litellm.completion(
        model=model_name,
        messages=messages,
        temperature=temperature,
        response_format={"type": "json_object"},
    )
    text = resp.choices[0].message.content or ""
    usage = resp.usage
    prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
    completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
    try:
        cost = float(litellm.completion_cost(resp, model=model_name))
    except Exception:
        cost = 0.0
    return text, prompt_tokens, completion_tokens, cost


def decompose(
    instance: dict,
    cfg: Config,
    *,
    complete_fn: CompleteFn | None = None,
    use_cache: bool = True,
) -> SlicePlan:
    """Return the (cached) SlicePlan for an instance, decomposing if needed."""
    instance_id = instance["instance_id"]

    if use_cache:
        cached = slice_cache.load(cfg, instance_id)
        if cached is not None:
            return cached

    fn = complete_fn or _litellm_complete
    issue_text = instance.get("problem_statement", "") or ""
    messages = render_orchestrator_messages(issue_text)

    last_err: Exception | None = None
    for _ in range(MAX_PARSE_RETRIES + 1):
        text, p_tok, c_tok, cost = fn(cfg.orchestrator_model, messages, 0.0)
        try:
            slices = slices_from_json(text)
        except Exception as e:  # noqa: BLE001 - bounded retry on malformed JSON
            last_err = e
            continue
        plan = SlicePlan(
            instance_id=instance_id,
            slices=slices,
            orchestrator_model=cfg.orchestrator_model,
            orchestrator_tokens=p_tok + c_tok,
            orchestrator_cost_usd=cost,
            cache_key=slice_cache.key_for(cfg, instance_id),
        )
        if use_cache:
            slice_cache.save(cfg, plan)
        return plan

    raise RuntimeError(f"orchestrator failed to produce valid slices for {instance_id}: {last_err}")
