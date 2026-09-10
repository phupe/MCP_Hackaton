# 03 — Resources and prompts

**Shows:** static resources, resource **templates**, MIME types, `ResourceError`, and prompts
that render either one message or a whole seeded conversation.
**Needs:** nothing.
**SDK reference:** [Resources](https://py.sdk.modelcontextprotocol.io/servers/resources/),
[URI templates](https://py.sdk.modelcontextprotocol.io/servers/uri-templates/),
[Prompts](https://py.sdk.modelcontextprotocol.io/servers/prompts/)

## Run it

```bash
uv run --with "mcp[cli]" mcp dev model_library_server.py
uv run pytest
```

The Inspector has a **Resources** tab and a **Prompts** tab. Note that this server has no tools
at all, and is still useful.

## Who decides

This is the distinction that trips up every first MCP server:

| Primitive | Who chooses to use it | Addressed by |
| --- | --- | --- |
| **tool** | the **model**, mid-reasoning | name |
| **resource** | the **application** (a host UI, an @-mention, your own code) | URI |
| **prompt** | a **person**, from a menu or a slash command | name |

A gene lookup the agent should decide to perform is a tool. The rule set of a model, which the
host should paste into context because the user opened it, is a resource. "Interpret this model
for a systems-biology audience", which the user picks deliberately, is a prompt.

Getting this wrong is the most common design mistake: people expose everything as tools, the tool
list grows to forty entries, and the model picks badly. **A large reference document should be a
resource, not a tool that returns it.**

## What to look at

### A template serves every record with one function

```python
@mcp.resource("models://{model_id}/spec", mime_type="application/json")
def model_spec(model_id: str) -> dict[str, object]: ...
```

The `{model_id}` placeholder must match the parameter name — get it wrong and the decorator
refuses **at import time**, not in production. Templates are advertised under
`resources/templates/list` rather than `resources/list`, because they are a pattern, not an
address. The test asserts exactly this split.

Your function runs on **read**, not on **list**. Expose a thousand resources and you pay only
for the ones somebody opens.

### Return types map to content types

`str` → text. `bytes` → a base64 blob. Anything else JSON-serialisable → JSON text. `mime_type=`
is a label you declare; the SDK never inspects your return value to guess it, so a `dict`
resource you forget to label is advertised as `text/plain`.

### A prompt can pre-fill the assistant's turn

`review_rule_change` returns three messages, the last one from the **assistant**. Pre-filling an
assistant turn is how you steer the model's next reply — here, into checking the node names and
attractors before agreeing to a rule change — without making the user type the steering.

## The point

Two of the three MCP primitives are not for the model to call. Reaching for them is usually what
turns a pile of tools into a server that is pleasant to use.

## Next

The remaining patterns are listed in [`../README.md`](../README.md) — we are choosing which ones
to build together.
