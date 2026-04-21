"""MCP server entrypoint — Server instance, dispatchers, lifecycle.

Supports two transports:
  - stdio (default): for Claude Code / claude_desktop_config.json
  - http:  for vibe coders, Cursor, web integrations, any HTTP client
"""
from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

import mcp.types as mcp_types
from mcp.server import Server
from mcp.server.stdio import stdio_server

# Import tools package for side-effect: every submodule @registers on import.
from core.mcp import tools as _tools  # noqa: F401
from core.mcp.helpers import err
from core.mcp.state import db
from core.mcp.tools._registry import TOOL_DEFS, TOOL_HANDLERS

log = logging.getLogger("fartrun.mcp")

server = Server("fartrun")

DEFAULT_HTTP_PORT = 3001


@server.list_tools()
async def list_tools() -> list[mcp_types.Tool]:
    # Defensive copy: callers shouldn't mutate the registry.
    return list(TOOL_DEFS)


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[mcp_types.TextContent]:
    handler = TOOL_HANDLERS.get(name)
    if handler is None:
        return err(f"Unknown tool: {name}")
    try:
        return await handler(arguments)
    except Exception as e:
        log.exception("tool %s failed", name)
        return err(f"{type(e).__name__}: {e}")


def _get_version() -> str:
    try:
        import tomllib
        pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
        with open(pyproject, "rb") as f:
            return tomllib.load(f).get("project", {}).get("version", "?")
    except Exception:
        return "?"


def _log_startup(transport: str, port: int | None = None) -> None:
    try:
        version = _get_version()
        d = db()
        extra = f", port={port}" if port else ""
        log.info(
            "fartrun MCP server starting (v%s, transport=%s%s, db=%s, tools=%d)",
            version, transport, extra, d.path, len(TOOL_DEFS),
        )
    except Exception as e:
        log.warning("startup banner failed: %s", e)


# ── stdio transport ──────────────────────────────────────────────────

async def _run_stdio() -> None:
    _log_startup("stdio")
    async with stdio_server() as (read, write):
        await server.run(read, write,
                         server.create_initialization_options())


# ── HTTP transport (SSE) ─────────────────────────────────────────────

async def _run_http(port: int) -> None:
    """Run MCP server over HTTP with SSE transport.

    Endpoints:
      POST /mcp — JSON-RPC calls (tool invocations)
      GET  /sse — Server-Sent Events stream (notifications)
    """
    from starlette.applications import Starlette
    from starlette.middleware.cors import CORSMiddleware
    from starlette.routing import Mount, Route
    from starlette.responses import JSONResponse
    from mcp.server.sse import SseServerTransport
    import uvicorn

    sse_transport = SseServerTransport("/mcp")

    async def handle_sse(request):
        async with sse_transport.connect_sse(
            request.scope, request.receive, request._send
        ) as (read, write):
            await server.run(read, write,
                             server.create_initialization_options())

    async def handle_health(request):
        return JSONResponse({
            "status": "ok",
            "server": "fartrun",
            "version": _get_version(),
            "tools": len(TOOL_DEFS),
            "transport": "http+sse",
        })

    app = Starlette(
        routes=[
            Route("/health", handle_health),
            Route("/sse", handle_sse),
            Mount("/mcp", app=sse_transport.handle_post_message),
        ],
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    _log_startup("http+sse", port)
    log.info("Endpoints: POST /mcp (JSON-RPC), GET /sse (events), GET /health")

    config = uvicorn.Config(
        app, host="0.0.0.0", port=port,
        log_level="info", access_log=False,
    )
    srv = uvicorn.Server(config)
    await srv.serve()


# ── entry points ─────────────────────────────────────────────────────

def main() -> None:
    """Run stdio MCP server. Used by `fartrun mcp` and Claude Code."""
    logging.basicConfig(
        level=logging.INFO,
        stream=sys.stderr,
        format="%(asctime)s %(name)s %(levelname)s: %(message)s",
    )
    asyncio.run(_run_stdio())


def main_http() -> None:
    """Run HTTP MCP server. Used by `fartrun mcp --http`."""
    import argparse
    parser = argparse.ArgumentParser(description="fartrun MCP HTTP server")
    parser.add_argument(
        "--port", type=int, default=DEFAULT_HTTP_PORT,
        help=f"HTTP port (default: {DEFAULT_HTTP_PORT})",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s: %(message)s",
    )
    asyncio.run(_run_http(args.port))
