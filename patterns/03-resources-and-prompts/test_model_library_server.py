import json

import pytest
from mcp import Client

from model_library_server import mcp


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def client():
    async with Client(mcp, raise_exceptions=True) as c:
        yield c


@pytest.mark.anyio
async def test_static_resources_are_listed_templates_are_not(client: Client) -> None:
    listed = {r.uri for r in (await client.list_resources()).resources}
    assert listed == {"models://index", "models://conventions"}

    templates = (await client.list_resource_templates()).resource_templates
    assert [t.uri_template for t in templates] == ["models://{model_id}/spec"]


@pytest.mark.anyio
async def test_read_templated_resource(client: Client) -> None:
    result = await client.read_resource("models://egfr-mapk/spec")
    spec = json.loads(result.contents[0].text)
    assert spec["title"] == "EGFR to MAPK cascade"
    assert spec["rules"]["ERK"] == "MEK"
    # The URI in the result is the concrete one that was asked for, not the template.
    assert result.contents[0].uri == "models://egfr-mapk/spec"


@pytest.mark.anyio
async def test_missing_model_raises_resource_error(client: Client) -> None:
    with pytest.raises(Exception, match="No model"):
        await client.read_resource("models://nope/spec")


@pytest.mark.anyio
async def test_prompt_renders_one_user_message(client: Client) -> None:
    result = await client.get_prompt("interpret_model", {"model_id": "apoptosis"})
    assert len(result.messages) == 1
    assert result.messages[0].role == "user"
    assert "models://apoptosis/spec" in result.messages[0].content.text


@pytest.mark.anyio
async def test_prompt_can_seed_a_whole_conversation(client: Client) -> None:
    result = await client.get_prompt(
        "review_rule_change",
        {"model_id": "apoptosis", "node": "Casp3", "new_rule": "TNF"},
    )
    assert [m.role for m in result.messages] == ["user", "user", "assistant"]
