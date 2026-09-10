import asyncio

from azure.ai.agentserver.responses import (
    CreateResponse,
    ResponseContext,
    ResponsesAgentServerHost,
    TextResponse,
)

history_app = ResponsesAgentServerHost()

def inspect_history_items(history):
    for i, item in enumerate(history):
        print(f"\n### Item {i}")
        print("type:", type(item).__name__)

        if hasattr(item, "role"):
            print("role:", item.role)

        if hasattr(item, "content"):
            print("content:", item.content)

        if hasattr(item, "id"):
            print("id:", item.id)

        print("raw:")
        print(item)
        
@history_app.response_handler
async def history_handler(
    request: CreateResponse,
    context: ResponseContext,
    _cancellation_signal: asyncio.Event,
):
    current_input = await context.get_input_text()
    history = await context.get_history()

    print("CURRENT INPUT:")
    print(current_input)

    print("\nHISTORY TYPE:")
    print(type(history))

    print("\nHISTORY LENGTH:")
    print(len(history))

    print("\nHISTORY:")
    inspect_history_items(history)

    return TextResponse(
        context,
        request,
        text=f"I received {len(history)} prior history items.",
    )
    
if __name__ == "__main__":
    history_app.run()