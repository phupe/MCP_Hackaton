# cBioPortal MCP Server

An MCP (Model Context Protocol) server that gives an LLM client (Claude Desktop,
Claude Code, etc.) tools to query [cBioPortal](https://www.cbioportal.org), the
public repository of cancer genomics study data, via its
[REST API](https://docs.cbioportal.org/web-api-and-clients/).

By default it talks to the public instance at `https://www.cbioportal.org/api`.
It can be pointed at any other cBioPortal deployment (e.g. an institutional one)
via environment variables — see [Configuration](#configuration).

## What it exposes

60 tools covering the main resources of the cBioPortal API:

- **Studies** — search/list studies, get details, tags, molecular profiles, sample lists
- **Samples & patients** — list/search/fetch, per-study and per-patient lookups
- **Clinical data & attributes** — study/sample/patient-level clinical data, multi-study fetch
- **Genes & gene panels** — search by symbol/alias, fetch by ID, gene panel contents
- **Molecular profiles** — the available data types per study (mutations, CNA, expression, ...)
- **Mutations** — by sample list or specific samples/genes, single- or multi-study
- **Molecular data** — expression/protein/methylation-style continuous values
- **Discrete copy number** & **copy number segments**
- **Generic assay data** (e.g. drug response) and **treatments**
- `raw_api_request` — an escape hatch to call any endpoint from the
  [Swagger UI](https://www.cbioportal.org/api/swagger-ui/index.html) not
  explicitly wrapped above (e.g. a full `StudyViewFilter`)

Most list/get endpoints support paging (`page_number`, `page_size`, `sort_by`,
`direction`) and a `projection` level of detail (`ID` < `SUMMARY` < `DETAILED`,
plus `META` for a result count).

## Setup

Requires Python 3.10+.

```bash
cd cbioportal-mcp
python -m venv .venv
.venv\Scripts\pip install -e .        # Windows
# source .venv/bin/activate && pip install -e .   # macOS/Linux
```

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `CBIOPORTAL_API_URL` | `https://www.cbioportal.org/api` | Base URL of the cBioPortal instance |
| `CBIOPORTAL_API_TOKEN` | *(none)* | Bearer token, if the instance requires auth |

## Running it standalone

```bash
.venv\Scripts\python -m cbioportal_mcp.server
```

This starts the server on stdio, waiting for an MCP client to connect.

## Using it from Claude Code

```bash
claude mcp add cbioportal -- "D:\MCP_Hackathon\cbioportal-mcp\.venv\Scripts\python.exe" -m cbioportal_mcp.server
```

## Using it from Claude Desktop

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "cbioportal": {
      "command": "D:\\MCP_Hackathon\\cbioportal-mcp\\.venv\\Scripts\\python.exe",
      "args": ["-m", "cbioportal_mcp.server"]
    }
  }
}
```

## Example prompts

- "Search cBioPortal for breast cancer studies from TCGA."
- "In the acc_tcga study, what mutations does TP53 have, and in how many samples?"
- "Compare mRNA expression of ERBB2 between two sample lists in a study."
- "What clinical attributes (e.g. survival, stage) are available for study X?"

## Project layout

```
cbioportal_mcp/
  client.py   # thin async HTTP client (httpx) for the cBioPortal REST API
  models.py   # small pydantic models for request-body identifiers (SampleIdentifier, etc.)
  server.py   # FastMCP server: tool definitions, one per API operation (or small group)
```
