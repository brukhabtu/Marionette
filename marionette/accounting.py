"""Per-role token/cost accounting.

Cost comes from the agent (`agent.cost`, already litellm-priced per the role's own
model). Token totals are recovered by walking the agent's messages: each assistant
message carries `extra.response.usage` with prompt/completion token counts.
"""

from __future__ import annotations

from .types import AgentRunResult, RoleAccounting


def tokens_from_messages(messages: list[dict]) -> int:
    """Sum prompt+completion tokens across all messages that report usage."""
    total = 0
    for m in messages:
        extra = m.get("extra") or {}
        response = extra.get("response") or {}
        usage = response.get("usage") if isinstance(response, dict) else None
        if isinstance(usage, dict):
            total += int(usage.get("prompt_tokens", 0) or 0)
            total += int(usage.get("completion_tokens", 0) or 0)
    return total


def accumulate(acct: RoleAccounting, res: AgentRunResult) -> None:
    """Fold one agent run into a running per-role tally (in place)."""
    acct.tokens += tokens_from_messages(res.messages)
    acct.cost_usd += res.cost
    acct.n_calls += res.n_calls
