# cBioPortal Public Data MCP Server

A read-only [MCP](https://modelcontextprotocol.io/) server for live queries to the public
[cBioPortal REST API](https://www.cbioportal.org/api/swagger-ui/index.html).

It exposes a focused workflow:

1. `get_study_data_catalog` returns the study's molecular profiles and sample lists.
2. `lookup_genes` resolves one or more Hugo symbols to Entrez IDs.
3. `fetch_mutations_by_study` discovers the mutation profile and sample list automatically.
4. `find_gene_alterations` scans a bounded set of studies and groups results by study.
5. `find_patients_with_mutation` returns the patients carrying an exact protein mutation in one
   study. It discovers the profile and mutation sample list in parallel, resolves the gene, then
   fetches the entire sequenced cohort in **four REST requests**. Optional requested clinical
   attributes are fetched in one additional batched request.
6. `assess_mutation_survival` compares overall survival between patients carrying an exact mutation
   and non-carriers using Kaplan-Meier medians and a two-sided log-rank test.

The higher-level alteration tools currently expose mutations. Copy-number and structural-variant
profiles are deliberately reported by `get_study_data_catalog` but are not queried implicitly:
their cBioPortal endpoints and result sizes differ, so they should be added with the same explicit
limits and typed output contract rather than silently broadening a mutation query.

The server never alters portal data. It uses `https://www.cbioportal.org/api` by default; set
`CBIOPORTAL_API_BASE_URL` to use another compatible cBioPortal instance.

`find_patients_with_mutation` matches `proteinChange` values exactly after normalizing letter case
and an optional `p.` prefix (for example, `V600E` and `p.V600E`). It returns the public patient and
sample identifiers plus mutation records; pass `clinical_attribute_ids` only when you need specific
patient-level clinical fields.

## Running

```bash
pip install -r requirements.txt
python server.py
```

## VS Code

Open the `cbioportal-mcp` directory as the VS Code workspace. The included
`.vscode/mcp.json` starts the server automatically through `uv`; no
`__main__.py` file is required. If VS Code asks for a server path, select
`server.py`.

You can also add the server manually with **MCP: Add Server** and use:

```text
uv run --no-project --quiet --with "mcp[cli]>=2.2.0" --with "httpx>=0.27" python /absolute/path/to/cbioportal-mcp/server.py
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
