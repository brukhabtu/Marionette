"""Mock worker model (DeterministicModel) and a mock orchestrator complete_fn.

The model emits, per slice, one edit action followed by a submit action. Each
assistant message carries a synthetic `extra.response.usage` so the token-split
accounting path is exercised, plus `extra.cost` for cost accounting.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .fixtures import MOCK_SLICE_EDITS, MOCK_SLICES_JSON

SUBMIT_CMD = "echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT"


def _output(content: str, command: str, *, cost: float, prompt_tokens: int, completion_tokens: int) -> dict:
    return {
        "role": "assistant",
        "content": content,
        "extra": {
            "actions": [{"command": command}],
            "cost": cost,
            "response": {"usage": {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens}},
        },
    }


def make_mock_model_factory(
    edits: list[str] | None = None,
    *,
    cost_per_call: float = 0.001,
    prompt_tokens: int = 100,
    completion_tokens: int = 20,
) -> Callable[[str, float], Any]:
    """Return a model_factory(model_name, temperature) -> DeterministicModel.

    The factory is stateful: it yields a model per call (one per slice) that applies
    the next edit, then submits. The edit index cycles modulo the edit list so the
    same factory produces consistent behaviour across multiple worker models, each
    of which restarts from the first edit at its first slice.
    """
    edit_cmds = edits if edits is not None else MOCK_SLICE_EDITS
    n = len(edit_cmds)
    state = {"call": 0}

    def factory(model_name: str, temperature: float) -> Any:
        from minisweagent.models.test_models import DeterministicModel

        i = state["call"] % n if n else 0
        state["call"] += 1
        edit = edit_cmds[i] if n else SUBMIT_CMD
        outputs = [
            _output(
                f"Applying slice {i + 1}.",
                edit,
                cost=cost_per_call,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            ),
            _output(
                "Slice complete; submitting.",
                SUBMIT_CMD,
                cost=cost_per_call,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            ),
        ]
        return DeterministicModel(outputs=outputs)

    return factory


def mock_orchestrator_complete(
    slices_json: str = MOCK_SLICES_JSON,
    *,
    prompt_tokens: int = 500,
    completion_tokens: int = 80,
    cost: float = 0.01,
) -> Callable[[str, list[dict], float], tuple[str, int, int, float]]:
    """Return a complete_fn for orchestrator.decompose that returns canned slices."""

    def complete(model_name: str, messages: list[dict], temperature: float):
        return slices_json, prompt_tokens, completion_tokens, cost

    return complete
