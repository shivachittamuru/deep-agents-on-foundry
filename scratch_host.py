import asyncio, os, tempfile
from langchain_core.messages import AIMessage
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.tools import tool

import deep_agents_foundry.agent as a
from deep_agents_foundry import hosting
from deep_agents_foundry.persistence import thread_config

class FakeModel(GenericFakeChatModel):
    def bind_tools(self, tools, **kwargs): return self

@tool
def noop(x: str) -> str:
    "noop"
    return x

os.environ["DEEP_AGENTS_SQLITE_PATH"] = os.path.join(tempfile.mkdtemp(), "host.db")
a.build_model = lambda: FakeModel(messages=iter([AIMessage(content="Streamed hosted answer")]))
a.build_web_search_tool = lambda: noop
hosting._agent_singleton = None

async def main():
    agent = await hosting._get_agent()
    cfg = thread_config("t1")
    deltas = [d async for d in hosting._stream_turn(agent, "hi", cfg)]
    print("DELTAS=", deltas)
    st = await agent.aget_state(cfg)
    print("MSGS=", len(st.values.get("messages", [])), "NEXT=", st.next)

asyncio.run(main())
