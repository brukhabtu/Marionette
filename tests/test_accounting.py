from marionette.accounting import accumulate, tokens_from_messages
from marionette.types import AgentRunResult, RoleAccounting


def _msg(prompt, completion, cost):
    usage = {"prompt_tokens": prompt, "completion_tokens": completion}
    return {
        "role": "assistant",
        "content": "x",
        "extra": {"cost": cost, "response": {"usage": usage}},
    }


def test_tokens_from_messages_sums_prompt_and_completion():
    msgs = [_msg(100, 20, 0.001), _msg(50, 10, 0.0005), {"role": "user", "content": "obs"}]
    assert tokens_from_messages(msgs) == 180


def test_tokens_ignores_messages_without_usage():
    assert tokens_from_messages([{"role": "system", "content": "s"}]) == 0


def test_accumulate_folds_runs():
    acct = RoleAccounting()
    r1 = AgentRunResult("Submitted", "", n_calls=2, cost=0.01, messages=[_msg(100, 20, 0.005)])
    r2 = AgentRunResult("Submitted", "", n_calls=3, cost=0.02, messages=[_msg(40, 10, 0.02)])
    accumulate(acct, r1)
    accumulate(acct, r2)
    assert acct.tokens == 170
    assert round(acct.cost_usd, 4) == 0.03
    assert acct.n_calls == 5
