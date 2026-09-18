"""Read-only MCP server entry point for the public cBioPortal REST API."""

from mcp.server import MCPServer
from app.tools import register_tools


mcp = MCPServer(
    "cBioPortal Public Data",
    instructions=(
        "Read-only tools for the public cBioPortal REST API. Use get_study_data_catalog to select "
        "a molecular profile and sample list, then use fetch_mutations_by_study or "
        "find_gene_alterations for "
        "bounded gene-centric mutation searches. "
        "Use find_patients_with_mutation to identify every patient in one study with an exact "
        "protein mutation; it queries the study's mutation sample list directly. "
        "Use assess_gene_mutation_survival when the question concerns a gene without naming a "
        "specific protein mutation. "
        "The server queries public cBioPortal data live and does not modify portal data."
    ),
)
register_tools(mcp)


if __name__ == "__main__":
    mcp.run()
