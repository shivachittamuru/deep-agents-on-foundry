"""Tests for Skills wiring (real skill files + fake model, no live calls)."""

from __future__ import annotations

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from langchain_core.tools import tool
from langgraph.store.memory import InMemoryStore
from deepagents.backends import FilesystemBackend

from deep_agents_foundry import agent as agent_module
from deep_agents_foundry.agent import RESEARCH_INSTRUCTIONS, build_research_agent
from deep_agents_foundry.memory import (
    ResearchContext,
    recall_research_preferences,
    remember_research_preference,
)
from deep_agents_foundry.skills import SKILLS_DIR, list_available_skills


class _FakeToolCallingModel(GenericFakeChatModel):
    def bind_tools(self, tools, **kwargs):
        return self


@tool
def _noop_search(query: str) -> str:
    """Test-only stand-in for web search."""
    return "no-op"


def _capture_create_deep_agent(monkeypatch):
    captured = {}
    monkeypatch.setattr(agent_module, "build_model", lambda: "MODEL")
    monkeypatch.setattr(agent_module, "build_web_search_tool", lambda: "WEB_SEARCH")
    monkeypatch.setattr(
        agent_module,
        "create_deep_agent",
        lambda **kwargs: captured.update(kwargs) or object(),
    )
    return captured


# --- 1. Skill files exist ---------------------------------------------------


def test_technology_research_skill_files_exist():
    tech = SKILLS_DIR / "technology-research"
    assert (tech / "SKILL.md").is_file()
    assert (tech / "architecture_checklist.md").is_file()
    assert (tech / "source_quality.md").is_file()


def test_architecture_comparison_skill_exists():
    assert (SKILLS_DIR / "architecture-comparison" / "SKILL.md").is_file()


# --- 2. Skill content sanity ------------------------------------------------


def test_technology_research_skill_content():
    text = (SKILLS_DIR / "technology-research" / "SKILL.md").read_text(
        encoding="utf-8"
    ).lower()

    for phrase in ("architecture", "state", "identity", "trade-offs", "primary sources"):
        assert phrase in text


# --- 3. Builder without Skills is unchanged ---------------------------------


def test_builder_without_skills_unchanged(monkeypatch):
    captured = _capture_create_deep_agent(monkeypatch)

    build_research_agent()

    assert "skills" not in captured
    assert "backend" not in captured
    assert captured["tools"] == ["WEB_SEARCH"]
    assert captured["system_prompt"] == RESEARCH_INSTRUCTIONS


# --- 4. Builder with Skills -------------------------------------------------


def test_builder_with_skills_wires_backend_without_prompt_bloat(monkeypatch):
    captured = _capture_create_deep_agent(monkeypatch)

    build_research_agent(skills=["."])

    assert captured["skills"] == ["."]
    assert isinstance(captured["backend"], FilesystemBackend)
    assert "WEB_SEARCH" in captured["tools"]
    # Skill bodies are NOT copied into the base prompt (progressive disclosure).
    assert captured["system_prompt"] == RESEARCH_INSTRUCTIONS


def test_builder_with_skills_and_checkpointer(monkeypatch):
    captured = _capture_create_deep_agent(monkeypatch)

    build_research_agent(skills=["."], checkpointer="CP")

    assert captured["skills"] == ["."]
    assert captured["checkpointer"] == "CP"


# --- 5. Memory + Skills + Checkpointer coexist ------------------------------


def test_skills_memory_and_checkpointer_coexist(monkeypatch):
    captured = _capture_create_deep_agent(monkeypatch)
    store = InMemoryStore()

    build_research_agent(store=store, skills=["."], checkpointer="CP")

    assert captured["store"] is store
    assert captured["context_schema"] is ResearchContext
    assert captured["skills"] == ["."]
    assert isinstance(captured["backend"], FilesystemBackend)
    assert captured["checkpointer"] == "CP"
    # Web search plus both memory tools remain present.
    assert "WEB_SEARCH" in captured["tools"]
    assert remember_research_preference in captured["tools"]
    assert recall_research_preferences in captured["tools"]


# --- 6. Skill routing metadata ----------------------------------------------


def test_technology_research_skill_is_discoverable():
    skills = {s.get("name"): s for s in list_available_skills()}

    assert "technology-research" in skills
    assert skills["technology-research"].get("description")


# --- 7. Behavioral: skills-enabled agent runs end to end --------------------


def test_skills_enabled_agent_runs_with_fake_model(monkeypatch):
    monkeypatch.setattr(
        agent_module,
        "build_model",
        lambda: _FakeToolCallingModel(messages=iter([AIMessage(content="done")])),
    )
    monkeypatch.setattr(agent_module, "build_web_search_tool", lambda: _noop_search)

    agent = build_research_agent(skills=["."])
    result = agent.invoke(
        {"messages": [{"role": "user", "content": "research quantum computing"}]}
    )

    assert result["messages"][-1].content == "done"


# --- 8. Simple request is not altered by enabling Skills --------------------


def test_base_instructions_do_not_contain_skill_bodies():
    # The base prompt stays small; skill procedures live in the skills library.
    assert "architecture_checklist" not in RESEARCH_INSTRUCTIONS
    assert "source_quality" not in RESEARCH_INSTRUCTIONS
