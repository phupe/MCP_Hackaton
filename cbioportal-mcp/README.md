# cBioPortal Public Data MCP Server

A read-only [MCP](https://modelcontextprotocol.io/) server for live queries to the public
[cBioPortal REST API](https://www.cbioportal.org/api/swagger-ui/index.html).

It exposes a focused workflow:

1. `list_studies` finds public study IDs.
2. `get_study_data_catalog` returns the study's molecular profiles and sample lists.
3. `list_study_samples` retrieves bounded pages of sample IDs.
4. `lookup_genes` resolves Hugo symbols to Entrez IDs.
5. `fetch_mutations` retrieves mutations for bounded, explicit sample and gene sets.

The server never alters portal data. It uses `https://www.cbioportal.org/api` by default; set
`CBIOPORTAL_API_BASE_URL` to use another compatible cBioPortal instance.

## Running

```bash
pip install -r requirements.txt
python server.py
```

For interactive inspection:

```bash
uv run --with "mcp[cli]" --with httpx mcp dev server.py
```

## API sources

- cBioPortal's [API and API Clients documentation](https://docs.cbioportal.org/web-api-and-clients/)
- Public [Swagger/OpenAPI reference](https://www.cbioportal.org/api/swagger-ui/index.html)

The API documentation also describes an official, hosted authenticated MCP endpoint. This project
is instead a local stdio server that wraps the public REST API, making it useful for MCP hosts
that do not connect directly to that hosted endpoint.
