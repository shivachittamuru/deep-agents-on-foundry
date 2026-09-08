from deep_agents_foundry import build_traced_research_agent

agent = build_traced_research_agent()

result = agent.invoke({
    "messages": [{
        "role": "user",
        "content": """
Research current Microsoft guidance for building custom agents in Foundry.

Use current Microsoft documentation.
Write important findings to /research_notes.md,
read the file back,
and then produce a concise architecture summary with citations.
"""
    }]
})

print(result["messages"][-1].content)


# uv run python scripts/test.py