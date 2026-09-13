"""Repository-anchored artifact paths shared by the offline tooling.

Both the improvement (P8C) and economics (P8D) frameworks persist compact JSON
under a single ``artifacts/`` directory at the repository root, so history lives
in one place regardless of the current working directory. The root is located by
walking up from this file to the directory containing ``pyproject.toml``; if that
is not found (e.g. an unusual install layout), the current directory is used.
"""

from __future__ import annotations

from pathlib import Path


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for candidate in (here, *here.parents):
        if (candidate / "pyproject.toml").is_file():
            return candidate
    return Path.cwd()


REPO_ROOT = _repo_root()
ARTIFACTS_DIR = REPO_ROOT / "artifacts"


def artifacts_dir(*parts: str) -> Path:
    """Return a path under the repository-root ``artifacts/`` directory."""
    return ARTIFACTS_DIR.joinpath(*parts)
