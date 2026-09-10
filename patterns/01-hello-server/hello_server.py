"""The smallest MCP server that does something a cancer biologist would recognise.

Run it:
    uv run --with "mcp[cli]" mcp dev hello_server.py
"""

from mcp.server import MCPServer

mcp = MCPServer("Cancer Gene Roles")

# A deliberately tiny, hard-coded panel. Real servers query a database;
# see patterns/09-live-api-ensembl for that. Here the data is beside the point.
ROLES = {
    "TP53": "tumour suppressor",
    "KRAS": "oncogene",
    "BRAF": "oncogene",
    "PTEN": "tumour suppressor",
    "RB1": "tumour suppressor",
}


@mcp.tool()
def gene_role(symbol: str) -> str:
    """Return whether a gene acts as an oncogene or a tumour suppressor."""
    return ROLES.get(symbol.upper(), f"{symbol.upper()} is not in this panel.")


if __name__ == "__main__":
    mcp.run()
