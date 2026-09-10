import asyncio

from azure.ai.agentserver.responses import (
    CreateResponse,
    ResponseContext,
    ResponsesAgentServerHost,
    TextResponse,
)

from deep_agents_foundry import build_research_agent


agent = build_research_agent()
app = ResponsesAgentServerHost()

def response_history_to_messages(history):
    messages = []

    for item in history:
        role = getattr(item, "role", None)
        content = getattr(item, "content", None)

        if role not in {"user", "assistant"}:
            continue

        if isinstance(content, str):
            text = content

        elif isinstance(content, list):
            parts = []

            for block in content:
                text = getattr(block, "text", None)

                if text:
                    parts.append(text)

            text = "\n".join(parts)

        else:
            continue

        if text.strip():
            messages.append(
                {
                    "role": role,
                    "content": text,
                }
            )

    return messages


@app.response_handler
async def handler(
    request: CreateResponse,
    context: ResponseContext,
    _cancellation_signal: asyncio.Event,
):
    user_input = await context.get_input_text() or ""

    history = await context.get_history()

    messages = response_history_to_messages(history)

    messages.append(
        {
            "role": "user",
            "content": user_input,
        }
    )

    result = await asyncio.to_thread(
        agent.invoke,
        {"messages": messages},
    )

    final_answer = result["messages"][-1].content[-1]["text"]

    return TextResponse(
        context,
        request,
        text=str(final_answer),
    )


if __name__ == "__main__":
    app.run()