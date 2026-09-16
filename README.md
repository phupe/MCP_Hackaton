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
| learn how to write an MCP server | [`plugins/`](plugins/) (each `plugins/demo-*/` is a one-feature server with its own README) and the [authoring skill](plugins/demo-skill/skills/authoring-an-mcp-server/SKILL.md) |
| see what already exists before you build | [`inventory/`](inventory/) |
| install the demo plugins into your own agent | [below](#install-the-demo-plugins) |

## What is in this repository

```
inventory/          what already exists: servers, skills, and the gaps
plugins/            six installable plugins: one skill, five one-feature MCP servers
tests/              structural checks that every plugin's manifests agree with each other
docs/               setup and background
scripts/            check_servers.py — launches every plugin's server over stdio
plugin.spec.json    the plugin decisions; input to the manifest generator
```

The repository is also a **marketplace** of six sibling plugins, each with its own manifests, so
the demo servers and skill work in whatever agent you already use.

## Install the demo plugins

Six plugins ship in this repository, all offline and instant — no API keys, no network:

| Plugin | What it shows | Try this |
| --- | --- | --- |
| [`demo-skill`](plugins/demo-skill/) | the Agent Skills syntax: one skill, `authoring-an-mcp-server` | "Help me write an MCP server for my own analysis." |
| [`demo-tools`](plugins/demo-tools/README.md) | tools `add`, `subtract`, `multiply`, `divide`; divide by zero raises `ToolError` so the model gets a readable error result | "Use demo-tools to divide 10 by 4, then divide 1 by 0." |
| [`demo-progress`](plugins/demo-progress/README.md) | tool `count_to` (10 one-second steps by default) with `ctx.report_progress` each step | "Use demo-progress to count to 10." |
| [`demo-elicitation`](plugins/demo-elicitation/README.md) | tool `greet` that asks the user their name via a `Resolve`/`Elicit` resolver; accept/decline/cancel; hosts without form elicitation get an MCP error | "Use demo-elicitation to greet me." |
| [`demo-prompt`](plugins/demo-prompt/README.md) | no tools, one prompt `summarise_gene(gene)`; in Claude Code it appears as `/demo-prompt:summarise_gene` | run the prompt for TP53 |
| [`demo-resource`](plugins/demo-resource/README.md) | no tools, resource `genes://panel` (JSON) and template `genes://panel/{symbol}`; in Claude Code it appears under `@` | "Read the resource genes://panel/KRAS from demo-resource." |

Each plugin directory has its own README with more detail; the table above links to them.

### Claude Code

```bash
claude plugin marketplace add sysbio-curie/MCP_Hackaton
claude plugin install demo-tools@sysbio-curie
```

or, inside a session:

```
/plugin marketplace add sysbio-curie/MCP_Hackaton
/plugin install demo-tools@sysbio-curie
```

Install several by repeating the install line, e.g. `claude plugin install demo-progress@sysbio-curie`.
Run `claude plugin list`, or `/mcp` inside a session, to check that a server connected.

From a local clone, load one plugin without installing it:

```bash
claude --plugin-dir plugins/demo-tools
```

### Codex

Unverified — the manifests are written to the published spec but have not been exercised with a
live Codex client:

```bash
codex plugin marketplace add sysbio-curie/MCP_Hackaton
codex plugin add demo-tools@sysbio-curie
```

### Agent Plugins 1.0 clients (Cursor, GitHub Copilot in VS Code, Kiro)

The [Agent Plugins 1.0](https://agent-plugins.org/specification) spec defines the package — each
`plugins/<name>/` directory is one — but installation is each client's own. In VS Code: Command
Palette → "Chat: Install Plugin from Source", which accepts either a Git URL or a local plugin
directory path (e.g. the absolute path of `plugins/demo-tools`).

VS Code local-path install: to be confirmed by the maintainer. It relies on the root
`plugin.json` files deliberately omitting `$schema` — see [Plugin formats](#plugin-formats) for
why. After changing a plugin you must reinstall it in VS Code: it keeps its own copy under
`~/Library/Application Support/Code/agentPlugins/` (macOS) and does not pick up edits to the
source directory on its own.

Cursor and Kiro: unverified.

### Any other MCP host

Copy the server entry out of `plugins/<name>/mcp.json` and replace `${PLUGIN_ROOT}` with the
absolute path of that plugin directory. For example, `demo-tools`:

```json
{
  "mcpServers": {
    "demo-tools": {
      "command": "uv",
      "args": ["run", "--no-project", "--quiet", "--with", "mcp>=2.1,<3",
               "python", "/path/to/MCP_Hackaton/plugins/demo-tools/tools_server.py"]
    }
  }
}
```

`uv run --with` builds the environment on first launch, so there is nothing to install first, and
because the server is the code in the tree — not a published package — editing it changes what
the plugin does.

## Plugin formats

One repository, one marketplace, six sibling plugins under `plugins/`, each self-contained with
its own manifests for every ecosystem, because the ecosystem has not converged:

| Format | Manifest | MCP config | Marketplace |
| --- | --- | --- | --- |
| [Agent Plugins 1.0](https://agent-plugins.org/specification) | `plugins/<name>/plugin.json` | `plugins/<name>/mcp.json` | `.agents/plugins/marketplace.json` |
| Claude Code | `plugins/<name>/.claude-plugin/plugin.json` | `plugins/<name>/.claude-plugin/mcp.json` | `.claude-plugin/marketplace.json` |
| Codex | `plugins/<name>/plugin.json` (with Codex extras under `extensions["com.openai"]`) | `plugins/<name>/mcp.json` | `.agents/plugins/marketplace.json` |

There is no `.codex-plugin/` folder — Codex reads the same `plugin.json` and `mcp.json` as the
open Agent Plugins format — and no root `.mcp.json`: Claude Code would read a root `.mcp.json` as
project configuration and never expand the placeholder. The only real difference between the two
MCP configs is the placeholder for the plugin's own directory — `${PLUGIN_ROOT}` in the open
format and Codex's, `${CLAUDE_PLUGIN_ROOT}` in Claude Code's.

Install strings have the shape `<plugin>@sysbio-curie`, e.g. `demo-tools@sysbio-curie`.

The root `plugin.json` files deliberately omit the Agent Plugins `$schema` key. VS Code 1.138.0 /
GitHub Copilot Chat 0.66.0 routes any `plugin.json` whose `$schema` starts with
`https://agent-plugins.org/schemas/` and ends with `/plugin.schema.json` to a "copilot native"
loader whose placeholder-substitution tables are empty and which sets no working directory, so
the server is launched as the literal string `${PLUGIN_ROOT}/tools_server.py` with cwd the home
directory and never starts (microsoft/vscode
[#303219](https://github.com/microsoft/vscode/issues/303219) and
[#305310](https://github.com/microsoft/vscode/issues/305310), both unfixed). Without a matching
`$schema`, VS Code falls through to its Claude-format loader (`.claude-plugin/plugin.json`),
which does substitute both `${CLAUDE_PLUGIN_ROOT}` and `${PLUGIN_ROOT}`, export them as
environment variables, and set cwd to the plugin directory — which is why installing from a local
path works there. This is the one place the tree is knowingly non-conformant with Agent Plugins
1.0: `tests/test_plugin_structure.py` gates the "plugin.json needs `$schema`" check on its
`AGENT_PLUGIN_SCHEMA_REQUIRED` constant (currently `False`) for exactly this reason. Once VS Code
fixes the loader, flip that constant to `True` and restore `"$schema":
"https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"` as the first key of each root
`plugins/<name>/plugin.json` (the spawning-agent-plugins generator writes it back on `spawn
--force`, or add it by hand).

**Verification status:** the Claude Code install path has been verified end to end on the
maintainer's machine. VS Code local-path install (Agent Plugins 1.0) is to be confirmed by the
maintainer now that the `$schema` omission above has landed. Codex is written to its published
spec only and has not been exercised with a live client.

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
[cheat sheet](plugins/demo-skill/skills/authoring-an-mcp-server/references/sdk-v2-cheatsheet.md)
covers the rest.

## Development

```bash
uv sync
uv run pytest                          # plugins/ and tests/
uv run python scripts/check_servers.py # launches every plugin's server over stdio
```

`tests/test_plugin_structure.py` is the structural checker from the spawning-agent-plugins skill:
it guards against drift such as a version mismatch between a plugin's manifests, a plugin missing
from the marketplace, or a root `.mcp.json` reappearing.

To regenerate the manifests after editing `plugin.spec.json`, use the spawning-agent-plugins
skill's generator. Three classes of hand-edit survive generation and a regeneration reports them
as `kept`, which is expected: the `${PLUGIN_ROOT}` placeholder in each `plugins/*/mcp.json`, the
relative-path `source` strings in `.claude-plugin/marketplace.json`, and the missing `$schema` in
each root `plugins/*/plugin.json` (see [Plugin formats](#plugin-formats)).

## Licence

MIT — see [`LICENSE`](LICENSE). *Organisers: confirm this is the intended licence for the
materials before the repository is shared with participants.*
