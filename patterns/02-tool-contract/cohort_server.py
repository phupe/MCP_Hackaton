"""Everything that makes a tool call itself correctly: constraints, enums,
a typed result, behavioural hints, and a failure the model can recover from.

Run it:
    uv run --with "mcp[cli]" mcp dev cohort_server.py
"""

from typing import Annotated, Literal

from pydantic import BaseModel, Field

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

mcp = MCPServer(
    "Toy Cohort",
    instructions=(
        "A toy cancer cohort with mutation calls for five genes across three tumour types. "
        "Use mutation_frequency to ask how often a gene is mutated in a tumour type."
    ),
)

TUMOUR_TYPES = ("BRCA", "LUAD", "COAD")

# gene -> tumour type -> (mutated samples, samples profiled)
COUNTS: dict[str, dict[str, tuple[int, int]]] = {
    "TP53": {"BRCA": (330, 1000), "LUAD": (460, 900), "COAD": (540, 850)},
    "KRAS": {"BRCA": (8, 1000), "LUAD": (290, 900), "COAD": (360, 850)},
    "PIK3CA": {"BRCA": (360, 1000), "LUAD": (60, 900), "COAD": (140, 850)},
    "APC": {"BRCA": (20, 1000), "LUAD": (40, 900), "COAD": (640, 850)},
    "BRAF": {"BRCA": (10, 1000), "LUAD": (65, 900), "COAD": (100, 850)},
}


class MutationFrequency(BaseModel):
    """The answer, as data the calling application can use without parsing prose."""

    gene: str
    tumour_type: str
    mutated: int = Field(description="Samples with at least one non-silent mutation.")
    profiled: int = Field(description="Samples with mutation data available.")
    frequency: float = Field(ge=0.0, le=1.0, description="mutated / profiled.")


@mcp.tool(
    title="Mutation frequency in a tumour type",
    annotations=ToolAnnotations(read_only_hint=True, open_world_hint=False),
)
def mutation_frequency(
    gene: Annotated[
        str,
        Field(description="HGNC gene symbol, e.g. TP53. Case-insensitive."),
    ],
    tumour_type: Literal["BRCA", "LUAD", "COAD"],
) -> MutationFrequency:
    """How often a gene is mutated in one tumour type of this toy cohort."""
    symbol = gene.strip().upper()
    if symbol not in COUNTS:
        # The model picked the argument, so the model gets to fix it.
        raise ToolError(
            f"{symbol!r} is not profiled in this cohort. "
            f"Available genes: {', '.join(sorted(COUNTS))}."
        )
    mutated, profiled = COUNTS[symbol][tumour_type]
    return MutationFrequency(
        gene=symbol,
        tumour_type=tumour_type,
        mutated=mutated,
        profiled=profiled,
        frequency=round(mutated / profiled, 4),
    )


@mcp.tool(annotations=ToolAnnotations(read_only_hint=True, open_world_hint=False))
def rank_genes(
    tumour_type: Literal["BRCA", "LUAD", "COAD"],
    limit: Annotated[int, Field(ge=1, le=5, description="How many genes to return.")] = 3,
) -> list[MutationFrequency]:
    """Rank this cohort's genes by mutation frequency in one tumour type."""
    rows = [mutation_frequency(gene, tumour_type) for gene in COUNTS]
    rows.sort(key=lambda r: r.frequency, reverse=True)
    return rows[:limit]


if __name__ == "__main__":
    mcp.run()
