# 01 — Hello server

**Shows:** the three lines that make an MCP server; how a tool gets its name, description
and schema; testing with the in-memory client.
**Needs:** nothing. No network, no API key.
**SDK reference:** [First steps](https://py.sdk.modelcontextprotocol.io/get-started/first-steps/),
[Testing](https://py.sdk.modelcontextprotocol.io/get-started/testing/)

## Run it

Inspect it in the browser:

```bash
uv run --with "mcp[cli]" mcp dev hello_server.py
```

Open the URL it prints, go to the **Tools** tab, and call `gene_role` with `KRAS`.

Run the tests:

```bash
uv run pytest
```

## What to look at

`hello_server.py` is 20 lines, and only three of them are MCP:

```python
mcp = MCPServer("Cancer Gene Roles")

@mcp.tool()
def gene_role(symbol: str) -> str:
    """Return whether a gene acts as an oncogene or a tumour suppressor."""
```

The SDK reads everything else off the function:

| What the model sees | Where it comes from |
| --- | --- |
| tool name `gene_role` | the function name |
| the description | the docstring |
| `{"symbol": {"type": "string"}}`, required | the type hints |
| `output_schema` `{"result": {"type": "string"}}` | the `-> str` return annotation |

You never write JSON Schema. **The signature is the contract**, and it is enforced before your
function runs: send `{"symbol": 42}` and the SDK rejects the call for you.

## The point

There is no MCP framework to learn before you can be useful. A server is a Python module with a
decorator on it. Everything else in this collection is a variation on these 20 lines.

The second thing worth internalising is the test. `Client(mcp)` connects **in-process** — no
subprocess, no port, no transport — so an MCP server is as testable as any other Python function.
Every pattern here ships tests for exactly this reason: on Day 2 you will change a tool and want
to know in one second whether it still works.

## Next

- **02 — Tool contract**: how to make a tool the model actually calls correctly.
