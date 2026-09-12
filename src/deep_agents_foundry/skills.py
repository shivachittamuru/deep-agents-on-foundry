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

from pathlib import Path

from deepagents.backends import FilesystemBackend
from deepagents.middleware.skills import _list_skills

# Repo-root skills directory (one level above the package's `src/`).
SKILLS_DIR = Path(__file__).resolve().parents[2] / "skills"

# A skill source is a parent directory scanned for skill subdirectories, so "."
# exposes the whole catalog; individual skill folders are not valid sources.
DEFAULT_SKILL_SOURCES = ["."]


def build_skills_backend(skills_dir: str | Path | None = None) -> FilesystemBackend:
    """Build the filesystem backend used to load skill files from disk."""
    root = Path(skills_dir) if skills_dir is not None else SKILLS_DIR
    return FilesystemBackend(root_dir=str(root))


def list_available_skills(skills_dir: str | Path | None = None):
    """Discover skill metadata (name + description) from the skills directory."""
    return _list_skills(build_skills_backend(skills_dir), ".")
