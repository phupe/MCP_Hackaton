# MCP patterns

Each subdirectory is a **standalone** MCP server that demonstrates one idea. Nothing imports
anything from another pattern: copy a directory out of this repo and it still runs. That is
deliberate — on Day 2 you will want to lift one of these as the starting point for your own
server.

All patterns target the **MCP Python SDK v2** (`mcp>=2.1`), which implements the
**2026-07-28** protocol revision. The v1 `FastMCP` class is gone; the entry point is
`from mcp.server import MCPServer`.

## Running a pattern

Every pattern runs on its own, with no repo setup at all:

```bash
cd patterns/01-hello-server
uv run --with "mcp[cli]" mcp dev hello_server.py
```

Or, from the repo root, with the shared environment and the tests:

```bash
uv sync
uv run pytest                        # every pattern
uv run pytest patterns/02-tool-contract   # just one
```

## Built

Read these three in order. They are ~120 lines of Python between them and they cover the whole
surface most Day 2 projects need.

| # | Pattern | Shows |
| --- | --- | --- |
| 01 | [hello-server](01-hello-server/) | the three lines that make a server; the in-memory test client |
| 02 | [tool-contract](02-tool-contract/) | `Field` constraints, `Literal` enums, typed results, `ToolError` |
| 03 | [resources-and-prompts](03-resources-and-prompts/) | resource templates, MIME types, prompts that seed a conversation |

## Proposed — we pick from here

The catalogue below is the shortlist for the rest of the collection, each mapped to the SDK
chapter it teaches and to a cancer-research use case that motivates it. **Nothing here is written
yet.** The organisers will select the demos to build before the materials ship.

Ticking every box is not the goal; a participant who has read 01–03 plus four or five of these
can build anything they proposed on Day 1.

| Candidate | Shows | Cancer-research framing |
| --- | --- | --- |
| `context-and-logging` | the injected `Context`, `ctx.read_resource`, `logging` to stderr | a tool that reads the server's own gene panel instead of duplicating it |
| `lifespan` | `lifespan=`, startup/shutdown, shared state | load a 200 MB expression matrix **once**, not per call |
| `progress` | `ctx.report_progress`, client `progress_callback` | a Boolean model simulation that reports which run it is on |
| `long-running-jobs` | tasks / polling for work that outlives one call | submit a PhysiBoSS run, poll it, fetch results |
| `elicitation` | `Resolve` + `Elicit` resolvers, accept/decline/cancel | confirm before overwriting a model, or disambiguate a gene alias |
| `sampling` | `ctx.session.create_message` — the server asking the *host's* LLM | summarise a free-text pathology note from inside a tool |
| `completions` | server-side autocomplete for prompt and template arguments | complete gene symbols and TCGA study codes as the user types |
| `media` | returning `Image` / `Audio` content | return a survival curve or a network diagram as a PNG |
| `pagination` | cursors over long lists | a cohort with 10 000 samples that must not arrive in one blob |
| `subscriptions` | `resources/subscribe`, change notifications | notify the agent when a re-analysis has finished |
| `structured-errors` | `ToolError` vs `MCPError` vs a crash, side by side | why the model must never see your SQL traceback |
| `http-transport` | `streamable-http`, mounting into an existing ASGI app | expose a lab server to colleagues instead of running it locally |
| `auth` | token verification, protecting a server | a server over patient-adjacent data |
| `middleware` | cross-cutting concerns | audit-log every tool call for a reproducibility trail |
| `low-level-server` | the escape hatch under `MCPServer` | hand-written JSON Schema when the decorators are not enough |
| `client` | writing an MCP **client**, not a server | drive your own server from a script, for benchmarking |
| `wrapping-a-cli` | subprocess, temp files, timeouts, argument hygiene | wrap `MaBoSS` or a Nextflow pipeline you already have |
| `wrapping-a-python-api` | wrapping a library you already depend on | expose `pyMaBoSS` or `scanpy` to an agent |
| `live-ensembl` **(network)** | `httpx`, timeouts, retries, caching, rate limits | real gene coordinates and IDs from the Ensembl REST API |
| `live-cbioportal` **(network)** | paginating a real API, honest failure | real mutation frequencies from cBioPortal |

Two of these are marked **(network)**: they call a real public API, so they are the only patterns
that can fail because of the venue wifi. Everything else ships with its own tiny fixture data and
runs offline.

## House style

If you add a pattern, follow the three that exist:

- One directory, one idea. The README names the idea in its first line.
- A distinctly named server module (`cohort_server.py`, not `server.py`) so every pattern can be
  imported in the same test run.
- Tests that assert the **protocol-visible** behaviour — the schema, `is_error`,
  `structured_content` — not just the Python function.
- Fixture data small enough to read in the file. The biology is the framing, not the payload.
