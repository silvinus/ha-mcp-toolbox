import asyncio, sys
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from mcp.client.sse import sse_client
URL = sys.argv[1]; TOK = sys.argv[2] if len(sys.argv) > 2 else None
H = {"Authorization": f"Bearer {TOK}"} if TOK else {}
async def run(kind):
    cm = streamablehttp_client(URL + "/mcp", headers=H) if kind == "http" else sse_client(URL + "/sse", headers=H)
    async with cm as streams:
        async with ClientSession(streams[0], streams[1]) as s:
            await s.initialize()
            tools = await s.list_tools()
            print(kind, [t.name for t in tools.tools])
            r = await s.call_tool("dire_bonjour", {"prenom": "Sylvain"}) if any(t.name=="dire_bonjour" for t in tools.tools) else await s.call_tool("pi_status", {})
            print(kind, r.content[0].text[:300])
for k in ("http", "sse"):
    try: asyncio.run(run(k))
    except BaseException as e: print(k, "ERROR", type(e).__name__, e)
