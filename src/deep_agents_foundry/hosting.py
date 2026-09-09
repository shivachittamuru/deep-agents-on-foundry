import asyncio

from azure.ai.agentserver.responses import (
    CreateResponse,
    ResponseContext,
    ResponsesAgentServerHost,
    TextResponse,
)

from .agent import build_research_agent


def create_host() -> ResponsesAgentServerHost:
    agent = build_research_agent()
    app = ResponsesAgentServerHost()

    @app.response_handler
    async def handler(
        request: CreateResponse,
        context: ResponseContext,
        _cancellation_signal: asyncio.Event,
    ):
        user_input = await context.get_input_text() or ""

        if not user_input.strip():
            return TextResponse(
                context,
                request,
                text="Please provide a research question.",
            )

        result = await asyncio.to_thread(
            agent.invoke,
            {
                "messages": [
                    {
                        "role": "user",
                        "content": user_input,
                    }
                ]
            },
        )

        final_answer = result["messages"][-1].content[-1]['text']

        return TextResponse(
            context,
            request,
            text=str(final_answer),
        )

    return app