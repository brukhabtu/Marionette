"""Mock environment: a real temp-dir git repo behind a LocalEnvironment.

Edits run as real shell commands and produce a real cumulative git diff, so the
worker's diff-extraction path is exercised for real — just without Docker.
"""

from __future__ import annotations

import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .fixtures import MOCK_SEED_FILES

EnvFactory = Callable[[dict], Any]

_GIT_ENV = {
    "GIT_AUTHOR_NAME": "mock",
    "GIT_AUTHOR_EMAIL": "mock@example.com",
    "GIT_COMMITTER_NAME": "mock",
    "GIT_COMMITTER_EMAIL": "mock@example.com",
}


def seed_repo(root: Path, files: dict[str, str]) -> None:
    """Create a git repo at root with the given files committed as the base."""
    root.mkdir(parents=True, exist_ok=True)
    for rel, content in files.items():
        fp = root / rel
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content)
    run = lambda *a: subprocess.run(  # noqa: E731
        ["git", *a], cwd=root, env={"PATH": _path(), **_GIT_ENV}, check=True, capture_output=True
    )
    run("init", "-q")
    run("add", "-A")
    run("commit", "-q", "-m", "base")


def _path() -> str:
    import os

    return os.environ.get("PATH", "/usr/bin:/bin")


def make_mock_env_factory(seed_files: dict[str, str] | None = None) -> EnvFactory:
    """Return an env_factory(instance) -> LocalEnvironment over a fresh temp repo.

    The same env object is reused across all of an instance's slices (the worker
    holds it), so edits accumulate exactly as they would in a Docker container.
    """
    files = seed_files if seed_files is not None else MOCK_SEED_FILES

    def factory(instance: dict) -> Any:
        from minisweagent.environments.local import LocalEnvironment

        tmp = Path(tempfile.mkdtemp(prefix=f"marionette-{instance['instance_id']}-"))
        seed_repo(tmp, files)
        return LocalEnvironment(cwd=str(tmp), env=_GIT_ENV)

    return factory
