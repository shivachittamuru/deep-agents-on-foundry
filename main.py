import asyncio
import sys

# psycopg async requires a SelectorEventLoop; Windows defaults to ProactorEventLoop.
# Only affects local `azd ai agent run` on Windows; the Linux container is unaffected.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from deep_agents_foundry.hosting import create_host


app = create_host()


if __name__ == "__main__":
    app.run()