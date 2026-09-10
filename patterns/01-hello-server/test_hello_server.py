"""The in-memory client is the whole testing story: no subprocess, no port."""

import pytest
from mcp import Client

from hello_server import mcp


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def client():
    async with Client(mcp, raise_exceptions=True) as c:
        yield c


@pytest.mark.anyio
async def test_lists_one_tool(client: Client) -> None:
    tools = await client.list_tools()
    assert [t.name for t in tools.tools] == ["gene_role"]


@pytest.mark.anyio
async def test_known_gene(client: Client) -> None:
    result = await client.call_tool("gene_role", {"symbol": "kras"})
    assert result.content[0].text == "oncogene"
    assert result.structured_content == {"result": "oncogene"}


@pytest.mark.anyio
async def test_unknown_gene_is_not_an_error(client: Client) -> None:
    # This server chooses to answer rather than fail. Pattern 04 argues the other way.
    result = await client.call_tool("gene_role", {"symbol": "NOTAGENE"})
    assert result.is_error is False
