"""Launch every server declared in mcp.json exactly as an MCP host would, over real stdio.

Use this to check that the plugin config in mcp.json actually works before you hand the
repo to anyone:

    PLUGIN_ROOT="$PWD" uv run python scripts/check_plugin.py

It exits non-zero if any server fails to start or complete the MCP handshake.
"""
import json, os, pathlib, anyio
from mcp import Client, StdioServerParameters

PLUGIN_ROOT = os.environ["PLUGIN_ROOT"]

def expand(v: str) -> str:
    return v.replace("${PLUGIN_ROOT}", PLUGIN_ROOT)

async def main() -> None:
    cfg = json.load(open(pathlib.Path(PLUGIN_ROOT) / "mcp.json"))
    failures = 0
    for name, spec in cfg["mcpServers"].items():
        params = StdioServerParameters(
            command=spec["command"],
            args=[expand(a) for a in spec.get("args", [])],
            env={**os.environ, **spec.get("env", {})},
        )
        try:
            async with Client(params) as c:
                tools = [t.name for t in (await c.list_tools()).tools]
                res = [r.uri for r in (await c.list_resources()).resources]
                tmpl = [t.uri_template for t in (await c.list_resource_templates()).resource_templates]
                prompts = [p.name for p in (await c.list_prompts()).prompts]
            print(f"OK   {name}")
            print(f"       tools:     {tools}")
            print(f"       resources: {res}  templates: {tmpl}")
            print(f"       prompts:   {prompts}")
        except Exception as e:
            failures += 1
            print(f"FAIL {name}: {type(e).__name__}: {e}")
    raise SystemExit(1 if failures else 0)

anyio.run(main)
