# Marionette

A cost/accuracy harness that measures how well a **cheap worker model** resolves real
GitHub issues when a **fixed larger orchestrator** decomposes each issue into scoped
slices. Each worker model lands on a cost-vs-accuracy frontier.

Spec: [`docs/specs/worker-on-slices-harness.md`](docs/specs/worker-on-slices-harness.md).

## How it works (per instance)

1. **Decompose** — the orchestrator (`claude-opus-4-8`, fixed) reads the issue text only
   and emits an ordered list of slices (`scope` + `target_files`). Produced once per
   instance, cached, and reused for every worker run.
2. **Execute** — for each slice, a fresh worker agent runs against the **same** SWE-bench
   instance container. Conversation resets per slice; file edits accumulate on disk via
   git. The worker sees the issue plus that slice's scope.
3. **Grade** — the cumulative `git diff` is graded by the SWE-bench harness against the
   instance's `FAIL_TO_PASS` + `PASS_TO_PASS`. Pass = both green.

Orchestrator and worker tokens/cost are tracked **per role**. One results row is written
per `(worker_model, instance_id)`.

## Install

```bash
pip install -e .          # Python 3.10–3.12
```

Real runs grade in Docker. On Apple Silicon, build instance images locally
(`--namespace ''`, arm64); pre-built images are x86.

## Usage

```bash
# 1. Find multi-file / multi-hunk Verified instances, then hand-pin ~10–20 IDs
#    into configs/instances.txt:
marionette discover

# 2. Build + cache slice plans (orchestrator only; no Docker, needs an API key):
marionette decompose

# 3. Run the sweep (worker per slice, in Docker) -> runs/results.jsonl:
marionette run

# 4. Plot the frontier -> runs/frontier.png:
marionette plot
```

### Dry run (no Docker, no LLM, no SWE-bench)

Exercises the full orchestration, accounting, results, and plotting logic against a
mock model and a real temp-git repo:

```bash
marionette run --dry-run --worker mock/haiku --worker mock/sonnet
marionette plot
```

## Configuration

Everything lives in [`configs/default.yaml`](configs/default.yaml): the fixed
orchestrator model, the worker model list (the variable axis — `claude-haiku-4-5` by
default), per-slice step/cost caps, the instance set, and Docker namespace/arch.

## Architecture

```
marionette/
  config.py        dataset.py       prompts.py
  orchestrator.py  slice_cache.py   (decompose + cache, keyed on model+prompt)
  msa_adapter.py   images.py        (adapters: mini-swe-agent / image-name parity)
  worker.py        accounting.py    (one agent per slice; per-role token/cost)
  grading.py       results.py       plot.py
  run.py           mock/            (CLI; Dockerless dry-run path)
```

The two riskiest integration boundaries are isolated behind adapters: `msa_adapter.py`
(mini-swe-agent, pinned `2.4.2`) and `images.py` (the worker container and the grader
must share one image tag, derived from swebench's own `make_test_spec`).

## Tests

```bash
ruff check . && mypy marionette && pytest tests/
```

All checks run without Docker or network (the dry-run mock path drives the real agent
loop). Real Docker grading runs on a machine with a Docker daemon.
