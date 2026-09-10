"""Resources and prompts: the two primitives the model does not choose to call.

A resource is data the *application* decides to load. A prompt is a template a *person*
picks from a menu. Neither is a tool.

Run it:
    uv run --with "mcp[cli]" mcp dev model_library_server.py
"""

from typing import Annotated

from pydantic import Field

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ResourceError
from mcp.server.mcpserver.prompts.base import AssistantMessage, Message, UserMessage

mcp = MCPServer("Boolean Model Library")

# A tiny library of Boolean signalling models, in the spirit of a MaBoSS .bnd file.
MODELS: dict[str, dict[str, object]] = {
    "apoptosis": {
        "title": "Minimal apoptosis switch",
        "nodes": ["TNF", "NFkB", "Casp3", "Apoptosis"],
        "rules": {
            "NFkB": "TNF & !Casp3",
            "Casp3": "TNF & !NFkB",
            "Apoptosis": "Casp3",
        },
        "reference": "toy model, not published",
    },
    "egfr-mapk": {
        "title": "EGFR to MAPK cascade",
        "nodes": ["EGF", "EGFR", "RAS", "RAF", "MEK", "ERK", "Proliferation"],
        "rules": {
            "EGFR": "EGF",
            "RAS": "EGFR",
            "RAF": "RAS",
            "MEK": "RAF",
            "ERK": "MEK",
            "Proliferation": "ERK",
        },
        "reference": "toy model, not published",
    },
}


@mcp.resource("models://index", mime_type="application/json")
def model_index() -> dict[str, str]:
    """The models available in this library, by identifier."""
    return {name: str(spec["title"]) for name, spec in MODELS.items()}


@mcp.resource("models://{model_id}/spec", mime_type="application/json")
def model_spec(model_id: str) -> dict[str, object]:
    """The full node list and Boolean rules of one model."""
    if model_id not in MODELS:
        raise ResourceError(f"No model {model_id!r}. Read models://index for the list.")
    return MODELS[model_id]


@mcp.resource("models://conventions", mime_type="text/markdown")
def conventions() -> str:
    """How the rules in this library are written."""
    return (
        "# Rule conventions\n\n"
        "- `&` is AND, `|` is OR, `!` is NOT.\n"
        "- A node with no rule is an input and stays at its initial value.\n"
        "- Node names are case-sensitive and match the `nodes` list.\n"
    )


@mcp.prompt(title="Interpret a Boolean model")
def interpret_model(
    model_id: Annotated[str, Field(description="A model id from models://index.")],
) -> str:
    """Ask for a biological reading of one model in the library."""
    return (
        f"Read the resource models://{model_id}/spec and models://conventions.\n\n"
        "Then, for a systems-biology audience: name the phenotype each attractor "
        "corresponds to, and identify which single node perturbation would most "
        "change the outcome. Be explicit about what the model cannot tell us."
    )


@mcp.prompt(title="Review a proposed rule change")
def review_rule_change(model_id: str, node: str, new_rule: str) -> list[Message]:
    """Seed a critical conversation about editing one rule of a model."""
    return [
        UserMessage(f"I want to change {node} in the {model_id} model to: {new_rule}"),
        UserMessage(f"The current model is in models://{model_id}/spec."),
        AssistantMessage(
            "Before I agree, I will check three things: whether the node names exist "
            "in the model, whether the change creates a new cycle, and what it does to "
            "the attractors. Let me read the model first."
        ),
    ]


if __name__ == "__main__":
    mcp.run()
