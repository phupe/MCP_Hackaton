import pytest
from mcp import Client

from cohort_server import mcp


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def client():
    async with Client(mcp, raise_exceptions=True) as c:
        yield c


@pytest.mark.anyio
async def test_structured_result_is_typed(client: Client) -> None:
    result = await client.call_tool(
        "mutation_frequency", {"gene": "tp53", "tumour_type": "COAD"}
    )
    assert result.structured_content == {
        "gene": "TP53",
        "tumour_type": "COAD",
        "mutated": 540,
        "profiled": 850,
        "frequency": 0.6353,
    }


@pytest.mark.anyio
async def test_unknown_gene_is_a_tool_error_the_model_can_read(client: Client) -> None:
    result = await client.call_tool(
        "mutation_frequency", {"gene": "EGFR", "tumour_type": "LUAD"}
    )
    assert result.is_error is True
    assert "not profiled in this cohort" in result.content[0].text
    assert "APC" in result.content[0].text  # the message names the valid options
    assert result.structured_content is None


@pytest.mark.anyio
async def test_bad_enum_is_rejected_before_the_tool_runs(client: Client) -> None:
    result = await client.call_tool(
        "mutation_frequency", {"gene": "TP53", "tumour_type": "GLIOMA"}
    )
    assert result.is_error is True


@pytest.mark.anyio
async def test_limit_constraint_is_enforced(client: Client) -> None:
    result = await client.call_tool("rank_genes", {"tumour_type": "BRCA", "limit": 99})
    assert result.is_error is True
    assert "less than or equal to 5" in result.content[0].text


@pytest.mark.anyio
async def test_ranking(client: Client) -> None:
    result = await client.call_tool("rank_genes", {"tumour_type": "COAD", "limit": 2})
    genes = [row["gene"] for row in result.structured_content["result"]]
    assert genes == ["APC", "TP53"]


@pytest.mark.anyio
async def test_read_only_hint_is_published(client: Client) -> None:
    tools = {t.name: t for t in (await client.list_tools()).tools}
    assert tools["mutation_frequency"].annotations.read_only_hint is True
    assert tools["mutation_frequency"].title == "Mutation frequency in a tumour type"
