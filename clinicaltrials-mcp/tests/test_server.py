import sys
from datetime import date
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
    async with Client(mcp, raise_exceptions=True) as c:
        yield c


def _study(nct_id: str, keywords: list[str] | None = None) -> dict[str, object]:
    return {
        "protocolSection": {
            "identificationModule": {"nctId": nct_id, "briefTitle": f"Trial {nct_id}"},
            "statusModule": {"overallStatus": "RECRUITING", "startDateStruct": {"date": "2025-06-01"}},
            "sponsorCollaboratorsModule": {"leadSponsor": {"name": "Some Institute"}},
            "conditionsModule": {"conditions": ["Melanoma"], "keywords": keywords or []},
            "designModule": {"phases": ["PHASE2"]},
            "armsInterventionsModule": {"interventions": [{"type": "DRUG", "name": "vemurafenib"}]},
        }
    }


@pytest.mark.anyio
async def test_search_recent_open_trials_builds_expected_query(
    client: Client, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_request(method: str, path: str, **kwargs: object) -> dict[str, object]:
        assert method == "GET"
        assert path == "/studies"
        params = kwargs["params"]
        assert params["query.cond"] == "melanoma"
        assert params["filter.overallStatus"] == "RECRUITING,NOT_YET_RECRUITING,ENROLLING_BY_INVITATION,ACTIVE_NOT_RECRUITING"
        assert params["sort"] == "StartDate:desc"
        assert params["pageSize"] == 5
        since, until = params["query.term"].removeprefix("AREA[StartDate]RANGE[").removesuffix("]").split(",")
        assert date.fromisoformat(until) == date.today()
        assert date.fromisoformat(since) < date.fromisoformat(until)
        return {
            "totalCount": 1,
            "studies": [_study("NCT01234567", keywords=["BRAF V600E mutation", "BRAF inhibitor"])],
        }

    monkeypatch.setattr(server, "_request", fake_request)
    result = await client.call_tool(
        "search_recent_open_trials", {"cancer_type": "melanoma", "years": 2, "max_results": 5}
    )

    trials = result.structured_content["trials"]
    assert len(trials) == 1
    trial = trials[0]
    assert trial["nct_id"] == "NCT01234567"
    assert trial["interventions"] == [{"intervention_type": "DRUG", "name": "vemurafenib"}]
    assert trial["candidate_target_genes"] == ["BRAF"]


def test_extract_candidate_genes_filters_mutations_and_jargon() -> None:
    keywords = ["BRAF V600E mutation", "Phase III", "FDA approved", "EGFR L858R", "GSK2118436"]
    assert server._extract_candidate_genes(keywords) == ["BRAF", "EGFR"]


@pytest.mark.anyio
async def test_get_trial_details_fetches_by_nct_id(client: Client, monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_request(method: str, path: str, **kwargs: object) -> dict[str, object]:
        assert (method, path) == ("GET", "/studies/NCT01234567")
        return _study("NCT01234567")

    monkeypatch.setattr(server, "_request", fake_request)
    result = await client.call_tool("get_trial_details", {"nct_id": "NCT01234567"})

    assert result.structured_content["nct_id"] == "NCT01234567"
    assert result.structured_content["overall_status"] == "RECRUITING"
