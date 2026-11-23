"""Generic MCP server: loads tool plugins and serves them over Streamable HTTP and SSE.

A plugin is a .py file exposing ``register(mcp)``. Plugins are loaded from the
built-in ``tools/`` folder and from ``/share/mcp-tools`` (editable on the Pi).
"""

import hmac
import importlib.util
import ipaddress
import json
import logging
import os
import pathlib
import sys

import uvicorn
from mcp.server.fastmcp import FastMCP

OPTIONS_PATH = pathlib.Path(os.environ.get("OPTIONS_PATH", "/data/options.json"))
BUILTIN_TOOLS = pathlib.Path(__file__).parent / "tools"
SHARE_TOOLS = pathlib.Path(os.environ.get("SHARE_TOOLS", "/share/mcp-tools"))
PORT = int(os.environ.get("PORT", "8765"))

options = json.loads(OPTIONS_PATH.read_text()) if OPTIONS_PATH.exists() else {}
logging.basicConfig(
    level=options.get("log_level", "info").upper(),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("mcp_toolbox")

mcp = FastMCP(
    "toolbox",
    instructions="Outils maison de Sylvain, hébergés sur le Raspberry Pi.",
    host="0.0.0.0",
    port=PORT,
    stateless_http=True,
)


def load_plugins(folder: pathlib.Path) -> None:
    if not folder.is_dir():
        log.info("No plugin folder at %s", folder)
        return
    for path in sorted(folder.glob("*.py")):
        if path.name.startswith("_"):
            continue
        try:
            spec = importlib.util.spec_from_file_location(f"plugin_{path.stem}", path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            module.register(mcp)
            log.info("Loaded plugin %s", path)
        except Exception:  # a broken plugin must not take the server down
            log.exception("Failed to load plugin %s", path)


class AuthMiddleware:
    """Trusted networks pass; everyone else needs ``Authorization: Bearer <token>``."""

    def __init__(self, app, token: str, trusted: list[str]):
        self.app = app
        self.token = token
        self.trusted = [ipaddress.ip_network(n, strict=False) for n in trusted]

    def _is_trusted(self, host: str | None) -> bool:
        if not host:
            return False
        try:
            ip = ipaddress.ip_address(host)
        except ValueError:
            return False
        return any(ip in net for net in self.trusted)

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        client = scope.get("client")
        if self._is_trusted(client[0] if client else None):
            return await self.app(scope, receive, send)
        headers = dict(scope.get("headers") or [])
        auth = headers.get(b"authorization", b"").decode()
        if self.token and hmac.compare_digest(auth, f"Bearer {self.token}"):
            return await self.app(scope, receive, send)
        log.warning("Rejected request from %s to %s", client, scope.get("path"))
        await send({"type": "http.response.start", "status": 401,
                    "headers": [(b"content-type", b"text/plain")]})
        await send({"type": "http.response.body", "body": b"Unauthorized"})


def build_app():
    app = mcp.streamable_http_app()          # /mcp (+ session manager lifespan)
    app.router.routes.extend(mcp.sse_app().routes)  # /sse and /messages/
    return AuthMiddleware(app, options.get("token", ""), options.get("trusted_networks", []))


if __name__ == "__main__":
    load_plugins(BUILTIN_TOOLS)
    load_plugins(SHARE_TOOLS)
    if not options.get("token"):
        log.warning("No token set: only trusted networks can connect")
    uvicorn.run(build_app(), host="0.0.0.0", port=PORT, log_level=options.get("log_level", "info"))
