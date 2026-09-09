import asyncio

from azure.ai.agentserver.responses import (
    CreateResponse,
    ResponseContext,
    ResponsesAgentServerHost,
    TextResponse,
)


app = ResponsesAgentServerHost()


@app.response_handler
async def handler(
    request: CreateResponse,
    context: ResponseContext,
    _cancellation_signal: asyncio.Event,
):
    user_input = await context.get_input_text() or ""

    reply = f"Echo from Hosted Agent: {user_input}"

    return TextResponse(
        context,
        request,
        text=reply,
    )


if __name__ == "__main__":
    app.run()