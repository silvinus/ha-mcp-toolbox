import asyncio, sys, json
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
async def main(url, tok, tool, args):
    async with streamablehttp_client(url + "/mcp", headers={"Authorization": f"Bearer {tok}"}) as (r, w, _):
        async with ClientSession(r, w) as s:
            await s.initialize()
            print("tools:", [t.name for t in (await s.list_tools()).tools])
            res = await s.call_tool(tool, json.loads(args))
            print("isError:", res.isError, "|", res.content[0].text[:400])
asyncio.run(main(*sys.argv[1:5]))
