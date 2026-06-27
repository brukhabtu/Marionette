# Marionette — Worker-on-Slices Cost/Accuracy Harness

## Goal
Measure how well a cheap worker model resolves real GitHub issues when a fixed
larger model decomposes each issue into scoped slices. Output: each worker model
placed on a cost-vs-accuracy frontier.

## How it works (per instance)
1. **Decompose (once per instance)** — Orchestrator reads the issue text and emits
   an ordered list of slices (`scope` + `target_files`). Produced once, cached, and
   reused for every worker run, so all workers get the identical slice plan.
2. **Execute** — Worker works the slices in order in one continuous mini-swe-agent
   session inside the instance container. The worker sees the issue plus the current
   slice scope; edits accumulate in place.
3. **Grade** — Submit the cumulative diff; grade against the instance's
   `FAIL_TO_PASS` + `PASS_TO_PASS`. Pass = both green.

## Build
- **Wrapper** around mini-swe-agent that runs the decomposition step (cached) before
  the worker loop and runs all slices in one container.
- **Orchestrator prompt** → slice list (`scope`, `target_files`).
- **Per-role accounting** — orchestrator and worker tokens/cost tracked separately.
- **Results row** per `(worker_model, instance_id)` — see schema.
- **Plot script** — resolve-rate vs cost, one point per worker model.

## Results schema
```
worker_model:        str
instance_id:         str
resolved:            bool    # FAIL_TO_PASS and PASS_TO_PASS both pass
status:              str     # resolved | wrong | hit_limit | error
worker_iterations:   int     # worker loop turns to submit
orchestrator_tokens: int     # per-instance constant (cached decomposition)
worker_tokens:       int
cost_usd:            float    # priced per-role, summed
```

## Fixed vs variable
- **Fixed across all runs:** orchestrator model + prompt, cached slice plan per
  instance, instance set, mini-swe-agent config.
- **Variable:** worker model only (swap via litellm model string).

**Pinned parameters**
- Decomposition input: issue text only (no repo access).
- Worker session: continuous; sees issue + current slice; edits accumulate.
- Worker cap: pin a step limit and per-instance cost limit (e.g. 50 steps / $1) —
  this sets the ceiling of the cost axis.
- Worker temperature: 0.

## Instance set
- ~10–20 SWE-bench **Verified** instances, filtered to multi-file / multi-hunk
  patches (single-concern fixes don't exercise decomposition).
- Pin the IDs; reuse the exact set for every run.
- Apple Silicon: build images locally with `--namespace ''` (pre-built images are
  x86). Start with a few instances.

## Stack
mini-swe-agent (worker loop, model-agnostic via litellm) · SWE-bench harness
(environments + grading) · Python.

## Non-goals
- No fail2pass construction — SWE-bench supplies it.
- No per-slice grading — instance-level only.
- No repeated runs / confidence intervals — single run over the instance set to start.
- No local-model serving, no fine-tuning / RL.
- No non-Python datasets.
- No harness beyond mini-swe-agent.
