"""Prompt text for the orchestrator (decomposition) and the per-slice worker.

`ORCHESTRATOR_PROMPT` is hashed into the slice-cache key, so any edit here
(under prompt_version v1) invalidates cached plans automatically.
"""

from __future__ import annotations

import json

from .types import Slice

# ---------------------------------------------------------------------------
# Orchestrator: issue text only -> ordered list of slices. No repo access.
# ---------------------------------------------------------------------------

ORCHESTRATOR_SYSTEM = (
    "You are a senior engineer who decomposes a GitHub issue into an ordered list "
    "of small, independently-actionable implementation slices for a junior worker. "
    "You see ONLY the issue text — no repository access. Infer likely target files "
    "from the issue. Keep slices minimal and ordered so edits build on each other."
)

ORCHESTRATOR_INSTRUCTION = """\
Decompose the following GitHub issue into an ordered list of slices.

Each slice has:
- "scope": one or two sentences describing exactly what to change in this slice.
- "target_files": a list of the file paths you expect this slice to touch (best guess).

Rules:
- Order slices so a worker can do them top-to-bottom; later slices may depend on earlier ones.
- Prefer 2-5 slices. Use a single slice only if the issue is genuinely one concern.
- Do NOT write code. Describe the change.

Respond with ONLY a JSON object of the form:
{"slices": [{"scope": "...", "target_files": ["path/a.py"]}, ...]}

ISSUE:
{issue_text}
"""


def render_orchestrator_messages(issue_text: str) -> list[dict]:
    return [
        {"role": "system", "content": ORCHESTRATOR_SYSTEM},
        {"role": "user", "content": ORCHESTRATOR_INSTRUCTION.replace("{issue_text}", issue_text)},
    ]


# Text whose hash participates in cache invalidation.
ORCHESTRATOR_PROMPT = ORCHESTRATOR_SYSTEM + "\n\n" + ORCHESTRATOR_INSTRUCTION


# ---------------------------------------------------------------------------
# Worker: issue + the current slice. One fresh agent.run() per slice; edits
# from earlier slices already live on disk in the repo.
# ---------------------------------------------------------------------------

WORKER_SYSTEM = """\
You are a software engineer fixing a GitHub issue inside a checked-out repository.
Work from the repository root ({{cwd}}). You make changes by running shell commands.

You are working ONE slice of a larger plan. Earlier slices may already be applied to
the working tree — build on what is there; do not revert prior changes. Focus only on
the current slice's scope. Do not modify test files.

When (and only when) the current slice is complete, submit by running a command whose
output's FIRST line is exactly:
COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT
For example:
echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT
"""

WORKER_INSTANCE = """\
# GitHub issue
{{issue_text}}

# Current slice ({{slice_index}} of {{slice_total}})
{{slice_scope}}

Likely files to edit: {{slice_files}}

Make only the changes for this slice, then submit.
"""


def render_worker_templates(issue_text: str, sl: Slice, index: int, total: int) -> tuple[str, str]:
    """Return (system_template, instance_template) Jinja strings for one slice.

    issue_text and slice fields are substituted as literals here (not left as Jinja
    vars) so the worker prompt is fully self-contained; `{{cwd}}` stays a Jinja var
    resolved by the agent's env template vars.
    """
    files = ", ".join(sl.target_files) if sl.target_files else "(infer from the issue)"
    instance = (
        WORKER_INSTANCE.replace("{{issue_text}}", issue_text)
        .replace("{{slice_scope}}", sl.scope)
        .replace("{{slice_files}}", files)
        .replace("{{slice_index}}", str(index + 1))
        .replace("{{slice_total}}", str(total))
    )
    return WORKER_SYSTEM, instance


def slices_from_json(text: str) -> list[Slice]:
    """Parse the orchestrator's JSON response into Slice objects.

    Tolerates a leading/trailing code fence or prose around the JSON object.
    """
    obj = _extract_json_object(text)
    raw_slices = obj.get("slices", [])
    if not isinstance(raw_slices, list) or not raw_slices:
        raise ValueError("orchestrator response had no slices")
    out: list[Slice] = []
    for s in raw_slices:
        scope = str(s["scope"]).strip()
        files = [str(f).strip() for f in s.get("target_files", []) if str(f).strip()]
        if scope:
            out.append(Slice(scope=scope, target_files=files))
    if not out:
        raise ValueError("orchestrator response produced zero valid slices")
    return out


def _extract_json_object(text: str) -> dict:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return json.loads(text[start : end + 1])
    raise ValueError("could not parse JSON object from orchestrator response")
