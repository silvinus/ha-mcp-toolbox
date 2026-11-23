import asyncio, sys
from mcp import ClientSession
from mcp.client.sse import sse_client
from mcp.client.streamable_http import streamablehttp_client
async def main(url, tok):
    h = {"Authorization": f"Bearer {tok}"}
    async with streamablehttp_client(url + "/mcp", headers=h) as (r, w, _):
        async with ClientSession(r, w) as s:
            await s.initialize(); print("/mcp   :", sorted(t.name for t in (await s.list_tools()).tools))
    async with sse_client(url + "/ha/sse", headers=h) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize(); tools = (await s.list_tools()).tools
            print("/ha/sse:", sorted(t.name for t in tools))
            res = await s.call_tool("couleur_tempo", {}); print("call via /ha:", res.content[0].text)
asyncio.run(main(*sys.argv[1:3]))
