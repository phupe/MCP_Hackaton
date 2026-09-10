# 02 — Tool contract

**Shows:** `Field` constraints, `Literal` enums, a Pydantic model as the return type,
`ToolAnnotations`, and `ToolError` — the five things that decide whether a model calls
your tool correctly.
**Needs:** nothing.
**SDK reference:** [Tools](https://py.sdk.modelcontextprotocol.io/servers/tools/),
[Structured Output](https://py.sdk.modelcontextprotocol.io/servers/structured-output/),
[Handling errors](https://py.sdk.modelcontextprotocol.io/servers/handling-errors/)

## Run it

```bash
uv run --with "mcp[cli]" mcp dev cohort_server.py
uv run pytest
```

In the Inspector, call `mutation_frequency` with gene `EGFR`. It is a valid gene symbol but it
is not in this cohort, and the error you get back is the whole lesson.

## What to look at

### Constraints are free self-correction

```python
tumour_type: Literal["BRCA", "LUAD", "COAD"]
limit: Annotated[int, Field(ge=1, le=5)] = 3
```

`limit=99` never reaches your function. The SDK rejects it and the model reads
`Input should be less than or equal to 5`, then retries with a legal value. One `le=5` bought
you a self-correcting agent. This is the cheapest reliability win available to you, and most
first MCP servers skip it.

### The return type is the output schema

`-> MutationFrequency` publishes an `output_schema`, so the result arrives twice:

```python
result.content             # JSON text — this is all the model reads
result.structured_content  # {"gene": "TP53", ..., "frequency": 0.6353}
```

`content` is for the model. `structured_content` is for the application around it — a notebook,
a dashboard, the next tool in a chain — which wants `0.6353`, not a sentence containing it.
Returning a bare `str` works, but then nothing downstream can use the number without re-parsing
your prose.

### `raise ToolError`, never `return "error: ..."`

```python
raise ToolError(f"{symbol!r} is not profiled in this cohort. Available genes: ...")
```

A **returned** error string has `is_error=False`: to the model and to every client UI, the tool
worked and that sentence was the answer. `raise` sets the flag. And note what the message
contains — the list of genes that *would* work. An error is a turn in the conversation, so spend
it telling the model how to succeed.

The rule for choosing: **could a smarter model have avoided this?** Yes → `ToolError`. No →
`MCPError` (the request itself is invalid; the host sees it, the model gets nothing).
Anything you did not anticipate crashes, is logged with a traceback, and the model is told only
that the call failed — your internals never leak to it.

### Annotations and `instructions`

`ToolAnnotations(read_only_hint=True, open_world_hint=False)` lets a host decide whether to ask
the user before running the tool. They are hints, not security — never rely on a client honouring
them. The `instructions=` on `MCPServer` is the one place to say what the server is *for*; hosts
put it in the system prompt.

## The point

A tool that works when you call it by hand and a tool an agent uses reliably are different
artefacts. The difference is almost entirely in this file: bounded arguments, enumerated choices,
a typed result, and error messages written for the caller who will read them.

## Next

- **03 — Resources and prompts**: the two primitives that are *not* for the model to call.
