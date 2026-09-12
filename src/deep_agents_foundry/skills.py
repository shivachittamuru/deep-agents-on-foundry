"""Skills wiring for the research agent (P8B).

Skills are procedural knowledge — "how should I perform this task type?" — loaded
via progressive disclosure: only skill names and descriptions reach the model's
context, while full skill bodies are read on demand. Skills are distinct from
tools (actions), memory (durable user facts), and subagents (delegation).

Skill files live in the repo-root `skills/` directory (authored separately from
this package). Loading them from disk requires a filesystem-backed source, so a
skills-enabled agent uses `FilesystemBackend` rooted at that directory. This is
unrelated to the LangGraph Store used for long-term user memory.
"""

from __future__ import annotations

import os
from pathlib import Path

from deepagents.backends import FilesystemBackend
from deepagents.middleware.skills import _list_skills

# Repo-root skills directory (one level above the package's `src/`).
SKILLS_DIR = Path(__file__).resolve().parents[2] / "skills"

# Env override for deployments where the skills folder is not repo-relative
# (e.g. a container where the package is installed and skills ship elsewhere).
SKILLS_DIR_ENV = "DEEP_AGENTS_SKILLS_DIR"

# A skill source is a parent directory scanned for skill subdirectories, so "."
# exposes the whole catalog; individual skill folders are not valid sources.
DEFAULT_SKILL_SOURCES = ["."]


def resolve_skills_dir(skills_dir: str | Path | None = None) -> Path:
    """Resolve the skills directory: explicit arg, then env override, then default.

    Falls back to the current working directory's `skills/` if the repo-relative
    default is absent (common in a deployed container whose CWD holds the app).
    """
    if skills_dir is not None:
        return Path(skills_dir)

    env_value = os.environ.get(SKILLS_DIR_ENV)
    if env_value:
        return Path(env_value)

    if SKILLS_DIR.is_dir():
        return SKILLS_DIR
    return Path.cwd() / "skills"


def skills_available(skills_dir: str | Path | None = None) -> bool:
    """True when the resolved skills directory contains at least one skill."""
    directory = resolve_skills_dir(skills_dir)
    return directory.is_dir() and any(directory.glob("*/SKILL.md"))


def build_skills_backend(skills_dir: str | Path | None = None) -> FilesystemBackend:
    """Build the filesystem backend used to load skill files from disk."""
    return FilesystemBackend(root_dir=str(resolve_skills_dir(skills_dir)))


def list_available_skills(skills_dir: str | Path | None = None):
    """Discover skill metadata (name + description) from the skills directory."""
    return _list_skills(build_skills_backend(skills_dir), ".")
