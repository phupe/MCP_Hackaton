"""Quick manual test harness for the cBioPortal MCP server.

Calls the running FastMCP instance in-process (no stdio transport involved),
so it's a fast way to check tool wiring and hit the real cBioPortal API
without needing an MCP client.

Usage:
    .venv\\Scripts\\python.exe scripts\\smoke_test.py                # run the default checks below
    .venv\\Scripts\\python.exe scripts\\smoke_test.py --list          # just list registered tools
    .venv\\Scripts\\python.exe scripts\\smoke_test.py get_gene '{"gene_id": "TP53"}'
"""

from __future__ import annotations

import asyncio
import json
import sys


async def run_default_checks() -> None:
    from cbioportal_mcp.server import client, mcp

    tools = await mcp.list_tools()
    print(f"Registered tools: {len(tools)}\n")

    checks = [
        ("get_api_info", {}),
        ("list_studies", {"keyword": "breast", "page_size": 3}),
        ("get_gene", {"gene_id": "TP53"}),
        (
            "fetch_mutations_in_molecular_profile",
            {
                "molecular_profile_id": "acc_tcga_mutations",
                "sample_list_id": "acc_tcga_all",
                "entrez_gene_ids": [7157],
                "page_size": 2,
            },
        ),
    ]
    for name, args in checks:
        print(f"--- {name}({args}) ---")
        result = await mcp.call_tool(name, args)
        print(result, "\n")

    await client.aclose()


async def run_single_tool(name: str, args: dict) -> None:
    from cbioportal_mcp.server import client, mcp

    print(await mcp.call_tool(name, args))
    await client.aclose()


async def list_tools() -> None:
    from cbioportal_mcp.server import client, mcp

    for t in await mcp.list_tools():
        print(t.name, "-", (t.description or "").splitlines()[0])
    await client.aclose()


if __name__ == "__main__":
    if len(sys.argv) == 1:
        asyncio.run(run_default_checks())
    elif sys.argv[1] == "--list":
        asyncio.run(list_tools())
    else:
        tool_name = sys.argv[1]
        tool_args = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
        asyncio.run(run_single_tool(tool_name, tool_args))
