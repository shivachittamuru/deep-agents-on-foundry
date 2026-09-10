import os
from pathlib import Path

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
    cancellation_signal,
):
    text = await context.get_input_text() or ""

    home = Path(os.environ["HOME"])
    file_path = home / "session-test.txt"

    if text == "write":
        file_path.write_text("hello from this hosted session")
        reply = f"Wrote file. Exists={file_path.exists()}"

    elif text == "read":
        if file_path.exists():
            reply = file_path.read_text()
        else:
            reply = "File does not exist."

    else:
        reply = "Use write or read."

    return TextResponse(context, request, text=reply)


if __name__ == "__main__":
    app.run()