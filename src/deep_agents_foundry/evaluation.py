"""Deterministic and rubric-based evaluation utilities from notebook 04.1.

Local, reusable evaluation logic only. Judge inference is never hidden: the
rubric evaluator requires an explicitly supplied judge model. No baseline-vs-deep
comparison, repeatability, economics, or cloud evaluation-job logic lives here
(those remain research code in notebook 04.2).
"""

from __future__ import annotations

import json

RESEARCH_RUBRIC = """
Evaluate the response from an enterprise technical research agent.

Score each dimension from 1 to 5.

1. TASK COMPLETION — 20%
Did the response answer all parts of the user's request?

2. RESEARCH COMPLETENESS — 20%
Did the agent investigate enough relevant aspects to support its conclusion?

3. EVIDENCE QUALITY — 15%
Did it rely on authoritative, current, relevant sources?

4. GROUNDING — 15%
Are factual claims supported by the evidence gathered?

5. SYNTHESIS — 15%
Did the agent transform research into useful conclusions rather than merely
repeat sources?

6. TOOL USE — 10%
Did it use web research and other available tools appropriately?

7. EFFICIENCY — 5%
Did the agent avoid clearly unnecessary searches, repeated work,
or excessive intermediate processing?

Return:

- a 1-5 score for each dimension
- a short reason for each score
- a weighted overall score from 1-5
- the most important improvement
"""


def extract_trajectory_features(messages) -> dict:
    """Summarize local (Deep Agents) and server-side (Foundry) tool activity."""
    server_tool_calls = 0
    local_tool_calls = []
    has_write_file = False
    has_read_file = False

    for message in messages:
        tool_calls = getattr(message, "tool_calls", None) or []
        for call in tool_calls:
            name = call.get("name")
            local_tool_calls.append(name)

            if name == "write_file":
                has_write_file = True
            if name == "read_file":
                has_read_file = True

        content_blocks = getattr(message, "content_blocks", None) or []
        for block in content_blocks:
            if block.get("type") == "server_tool_call":
                server_tool_calls += 1

    return {
        "server_tool_calls": server_tool_calls,
        "local_tool_calls": local_tool_calls,
        "has_write_file": has_write_file,
        "has_read_file": has_read_file,
    }


def aggregate_usage(messages) -> dict:
    """Sum token usage across all messages that carry usage metadata."""
    input_tokens = 0
    output_tokens = 0
    total_tokens = 0

    for message in messages:
        usage = getattr(message, "usage_metadata", None)
        if not usage:
            continue

        input_tokens += usage.get("input_tokens", 0)
        output_tokens += usage.get("output_tokens", 0)
        total_tokens += usage.get("total_tokens", 0)

    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
    }


def has_citation_like_content(message) -> bool:
    """Heuristic: does the message look like it contains a citation or source?"""
    text = str(getattr(message, "content", message))

    return (
        "http" in text
        or "cite" in text.lower()
        or "source" in text.lower()
    )


def trajectory_summary(messages, *, elapsed_seconds: float | None = None) -> dict:
    """Compact trajectory view suitable for feeding into the rubric prompt."""
    features = extract_trajectory_features(messages)

    return {
        "server_search_calls": features["server_tool_calls"],
        "local_tools": features["local_tool_calls"],
        "elapsed_seconds": (
            round(elapsed_seconds, 2) if elapsed_seconds is not None else None
        ),
    }


def deterministic_evaluation(
    messages,
    *,
    expects_search: bool,
    expects_file: bool,
    elapsed_seconds: float | None = None,
) -> dict:
    """Run the exact-verifiable checks from notebook 04.1 over a message list."""
    trajectory = extract_trajectory_features(messages)
    final_message = messages[-1] if messages else None

    checks = {}

    checks["completed"] = bool(getattr(final_message, "content", None))

    if expects_search:
        checks["searched_when_expected"] = trajectory["server_tool_calls"] > 0

    if expects_file:
        checks["wrote_file"] = trajectory["has_write_file"]
        checks["read_file"] = trajectory["has_read_file"]

    if expects_search:
        checks["citations_present"] = (
            has_citation_like_content(final_message)
            if final_message is not None
            else False
        )

    checks["elapsed_seconds"] = elapsed_seconds
    checks["server_tool_calls"] = trajectory["server_tool_calls"]

    return checks


def build_rubric_prompt(
    query: str,
    response: str,
    *,
    trajectory_summary: dict | None = None,
) -> str:
    """Construct the judge prompt from the research rubric, task, and response."""
    sections = [
        RESEARCH_RUBRIC.strip(),
        f"USER TASK:\n{query}",
        f"AGENT RESPONSE:\n{response}",
    ]

    if trajectory_summary is not None:
        sections.append(
            "TRAJECTORY SUMMARY:\n" + json.dumps(trajectory_summary, indent=2)
        )
        sections.append(
            "When scoring efficiency and tool use,\n"
            "consider the trajectory as well as the final answer."
        )

    sections.append("Return valid JSON.")

    return "\n\n".join(sections) + "\n"


def _message_text(result) -> str:
    """Extract text from a judge model response (string or content-block list)."""
    content = getattr(result, "content", result)

    if isinstance(content, str):
        return content

    if isinstance(content, list):
        return "".join(
            block.get("text", "")
            for block in content
            if isinstance(block, dict)
        )

    return str(content)


def parse_judge_json(text: str) -> dict:
    """Parse JSON from a judge response, tolerating Markdown code fences."""
    raw = text.strip()

    if raw.startswith("```"):
        lines = raw.splitlines()
        raw = "\n".join(
            lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
        ).strip()

    json_start = min(
        (index for index in (raw.find("{"), raw.find("[")) if index >= 0),
        default=-1,
    )
    if json_start < 0:
        raise ValueError(f"No JSON object found in judge response: {text!r}")

    decoded, _ = json.JSONDecoder().raw_decode(raw[json_start:])
    return decoded


def evaluate_with_rubric(
    judge_model,
    query: str,
    response: str,
    *,
    trajectory_summary: dict | None = None,
) -> dict:
    """Score a response against the research rubric using an explicit judge model."""
    prompt = build_rubric_prompt(
        query, response, trajectory_summary=trajectory_summary
    )
    result = judge_model.invoke(prompt)
    return parse_judge_json(_message_text(result))
