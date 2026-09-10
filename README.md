# Hacking Cancer Research with LLM-based Agents and the Model Context Protocol

Teaching materials and shared workspace for the hackathon at **Institut Curie, Paris,
17–18 September 2026**.

> **Dates** Thursday 17 (13:00) – Friday 18 September 2026 · **Location** Institut Curie,
> 11 Pierre et Marie Curie, BDD building, Annexes, ground floor · **Organisers** Laurence
> Calzone (Institut Curie) and Eliott Jacopin (RIKEN)

Everything here is aimed at beginners with LLM-based agents and MCP. No prior experience with
agents, MCP or software engineering at large is assumed.

## Start here

| If you want to… | Go to |
| --- | --- |
| get your laptop ready before the event | [`docs/setup.md`](docs/setup.md) |
| learn how to write an MCP server | [`patterns/`](patterns/) |
| see what already exists before you build | [`inventory/`](inventory/) |
| install the demo servers into your own agent | [below](#install-the-demo-servers) |

## What is in this repository

```
patterns/     standalone MCP servers, one idea each, all tested        <- the teaching material
inventory/    what already exists: servers, skills, and the gaps
skills/       Agent Skills, shipped as part of the plugin
docs/         setup and background
scripts/      check_plugin.py — verifies the plugin config actually launches
```

The repository is also an **installable plugin**, in three formats, so the demo servers work in
whatever agent you already use.

## Install the demo servers

Three MCP servers ship with the plugin, all offline and instant — no API keys, no network:

| Server | What it exposes |
| --- | --- |
| `curie-gene-roles` | one tool: oncogene or tumour suppressor, over a five-gene panel |
| `curie-toy-cohort` | mutation frequencies and gene ranking over a toy three-tumour-type cohort |
| `curie-model-library` | two Boolean signalling models as **resources**, plus two **prompts** |

### Claude Code

```bash
/plugin marketplace add sysbio-curie/MCP_Hackaton
/plugin install curie-mcp-kit@curie-mcp-hackathon
```

### Codex, or any agent reading the open Agent Plugins format

Clone the repository and point your agent at it as a local plugin; the root
[`plugin.json`](plugin.json) and [`mcp.json`](mcp.json) conform to
[Agent Plugins 1.1.0](https://agent-plugins.org/specification).

### Any other MCP host

Copy an entry out of [`mcp.json`](mcp.json) into your host's configuration and replace
`${PLUGIN_ROOT}` with the path where you cloned this repository. For example:

```json
{
  "mcpServers": {
    "curie-toy-cohort": {
      "command": "uv",
      "args": ["run", "--quiet", "--with", "mcp>=2.1,<3",
               "python", "/path/to/MCP_Hackaton/patterns/02-tool-contract/cohort_server.py"]
    }
  }
}
```

`uv run --with` builds the environment on first launch, so there is nothing to install first.

Verify that all three start correctly:

```bash
PLUGIN_ROOT="$PWD" uv run python scripts/check_plugin.py
```

## Plugin formats

One repository, three manifests, because the ecosystem has not converged:

| Format | Manifest | MCP config | Marketplace |
| --- | --- | --- | --- |
| [Agent Plugins 1.1.0](https://agent-plugins.org/specification) | `plugin.json` | `mcp.json` | `.agents/plugins/marketplace.json` |
| Claude Code | `.claude-plugin/plugin.json` | `.mcp.json` | `.claude-plugin/marketplace.json` |
| Codex | `.codex-plugin/plugin.json` | `mcp.json` | `.agents/plugins/marketplace.json` |

They coexist without conflict: the filenames differ, and `skills/` is shared because all three
consume the same [Agent Skills](https://agentskills.io/specification) format. The only real
difference is the placeholder for the plugin's own directory — `${PLUGIN_ROOT}` in the open
format, `${CLAUDE_PLUGIN_ROOT}` in Claude Code.

`plugin.json` and `mcp.json` are validated against the official Agent Plugins 1.1.0 JSON
Schemas.

## Which SDK version

All material targets the **MCP Python SDK v2** (`mcp>=2.1`, currently 2.1.1), which implements
the **2026-07-28** protocol revision. If a tutorial you find elsewhere says
`from mcp.server.fastmcp import FastMCP`, it is written for v1 and the entry point has changed:

```python
from mcp.server import MCPServer
```

Two consequences worth knowing before you start: `resource.uri` is a plain `str` rather than an
`AnyUrl`, and there are no server-initiated requests, so `ctx.elicit()` only works on legacy
connections — use a `Resolve(...)` resolver instead. The
[cheat sheet](skills/authoring-an-mcp-server/references/sdk-v2-cheatsheet.md) covers the rest.

## Development

```bash
uv sync
uv run pytest                                              # every pattern
PLUGIN_ROOT="$PWD" uv run python scripts/check_plugin.py    # every plugin server
```

## Licence

MIT — see [`LICENSE`](LICENSE). *Organisers: confirm this is the intended licence for the
materials before the repository is shared with participants.*
