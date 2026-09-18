import sys
from pathlib import Path

import pytest
from mcp import Client

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import server  # noqa: E402
from server import mcp  # noqa: E402


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def client():
    async with Client(mcp, raise_exceptions=True) as current_client:
        yield current_client


@pytest.mark.anyio
async def test_search_studies_by_gene_queries_gdc_mutations(
    client: Client, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_request(method: str, path: str, **kwargs: object) -> list[dict[str, object]]:
        if path == "/ssm":
            assert kwargs["params"]["fields"] == "cases.project.project_id"
            return {"data": {"hits": [{"cases": [{"project": [{"project_id": "TCGA-BRCA"}]}]}]}}
        assert path == "/projects"
        return {"data": {"hits": [{"project_id": "TCGA-BRCA", "name": "Breast Cancer"}]}}

    monkeypatch.setattr(server, "_request", fake_request)
    result = await client.call_tool("search_studies_by_gene", {"gene_symbol": "TP53"})

    assert result.structured_content["query_type"] == "gene"
    assert [study["study_id"] for study in result.structured_content["studies"]] == ["TCGA-BRCA"]


@pytest.mark.anyio
async def test_search_studies_by_disease_returns_normalized_study(
    client: Client, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_request(method: str, path: str, **kwargs: object) -> list[dict[str, object]]:
        assert path == "/projects"
        assert "breast cancer" in kwargs["params"]["filters"]
        return {"data": {"hits": [
            {
                "project_id": "TCGA-BRCA",
                "name": "Breast Invasive Carcinoma",
                "disease_type": "Breast Cancer",
                "primary_site": "Breast",
            }
        ]}}

    monkeypatch.setattr(server, "_request", fake_request)
    result = await client.call_tool("search_studies_by_disease", {"disease": "breast cancer"})

    assert result.structured_content["studies"] == [
        {
            "study_id": "TCGA-BRCA",
            "name": "Breast Invasive Carcinoma",
            "description": "Breast Cancer",
            "cancer_type_id": "Breast",
            "sample_count": None,
            "reference_genome": None,
        }
    ]
