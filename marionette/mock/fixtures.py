"""Canned data for dry-runs and tests."""

from __future__ import annotations

# A canned instance whose gold patch is multi-file (passes the dataset filter).
MOCK_INSTANCE = {
    "instance_id": "mockorg__mockrepo-1",
    "repo": "mockorg/mockrepo",
    "base_commit": "0" * 40,
    "problem_statement": (
        "Title: greeter and farewell are inconsistent\n\n"
        "The greet() function should say 'hello world' and the farewell() function "
        "should say 'goodbye world'. Both currently return placeholders."
    ),
    "patch": (
        "diff --git a/greet.py b/greet.py\n@@ -1 +1 @@\n-pass\n+return 'hello world'\n"
        "diff --git a/farewell.py b/farewell.py\n@@ -1 +1 @@\n-pass\n+return 'goodbye world'\n"
    ),
    "test_patch": "diff --git a/test_x.py b/test_x.py\n@@ -0,0 +1 @@\n+assert True\n",
    "FAIL_TO_PASS": ["test_x.py::test_greet", "test_x.py::test_farewell"],
    "PASS_TO_PASS": ["test_x.py::test_imports"],
    "version": "1.0",
    "environment_setup_commit": "0" * 40,
}

# Seed files written into the mock repo before the worker runs.
MOCK_SEED_FILES = {
    "greet.py": "def greet():\n    return 'TODO'\n",
    "farewell.py": "def farewell():\n    return 'TODO'\n",
}

# Canned slice plan JSON (what the mock orchestrator "returns").
MOCK_SLICES_JSON = (
    '{"slices": ['
    '{"scope": "Make greet() return hello world", "target_files": ["greet.py"]}, '
    '{"scope": "Make farewell() return goodbye world", "target_files": ["farewell.py"]}'
    "]}"
)

# Shell edits the mock worker applies, one per slice (real commands run in the repo).
MOCK_SLICE_EDITS = [
    "python -c \"open('greet.py','w').write(\\\"def greet():\\n    return 'hello world'\\n\\\")\"",
    "python -c \"open('farewell.py','w').write(\\\"def farewell():\\n    return 'goodbye world'\\n\\\")\"",
]

# Canned grading reports (per-instance report.json shapes).
REPORT_RESOLVED = {
    MOCK_INSTANCE["instance_id"]: {
        "resolved": True,
        "tests_status": {
            "FAIL_TO_PASS": {"success": MOCK_INSTANCE["FAIL_TO_PASS"], "failure": []},
            "PASS_TO_PASS": {"success": MOCK_INSTANCE["PASS_TO_PASS"], "failure": []},
        },
    }
}

REPORT_UNRESOLVED = {
    MOCK_INSTANCE["instance_id"]: {
        "resolved": False,
        "tests_status": {
            "FAIL_TO_PASS": {"success": [], "failure": MOCK_INSTANCE["FAIL_TO_PASS"]},
            "PASS_TO_PASS": {"success": MOCK_INSTANCE["PASS_TO_PASS"], "failure": []},
        },
    }
}
