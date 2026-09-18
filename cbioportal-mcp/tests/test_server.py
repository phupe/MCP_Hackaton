import sys
from pathlib import Path

import pytest
from mcp import Client

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import server  # noqa: E402
from app import api  # noqa: E402
from server import mcp  # noqa: E402


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def client():
    async with Client(mcp, raise_exceptions=True) as c:
        yield c


@pytest.mark.anyio
async def test_list_studies_returns_normalized_studies(client: Client, monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_request(method: str, path: str, **kwargs: object) -> list[dict[str, object]]:
        assert method == "GET"
        assert path == "/studies"
        assert kwargs["params"] == {
            "pageNumber": 0,
            "pageSize": 25,
            "projection": "SUMMARY",
            "sortBy": "name",
            "direction": "ASC",
        }
        return [{"studyId": "study_a", "name": "Study A", "allSampleCount": 4}]

    monkeypatch.setattr(api, "request", fake_request)
    result = await client.call_tool("list_studies", {})

    assert result.structured_content["studies"] == [
        {
            "study_id": "study_a",
            "name": "Study A",
            "description": None,
            "cancer_type_id": None,
            "sample_count": 4,
            "reference_genome": None,
        }
    ]


@pytest.mark.anyio
async def test_search_studies_adds_filters(client: Client, monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_request(method: str, path: str, **kwargs: object) -> list[dict[str, object]]:
        assert (method, path) == ("GET", "/studies")
        assert kwargs["params"] == {
            "pageNumber": 0,
            "pageSize": 25,
            "projection": "SUMMARY",
            "sortBy": "name",
            "direction": "ASC",
            "keyword": "BRCA1",
            "cancerTypeId": "nbl",
        }
        return [{"studyId": "nbl_a", "name": "Pediatric Neuroblastoma", "allSampleCount": 2}]

    monkeypatch.setattr(api, "request", fake_request)
    result = await client.call_tool(
        "search_studies", {"keyword": "BRCA1", "cancer_type_id": "nbl", "filter_text": "pediatric"}
    )

    assert result.structured_content["studies"][0]["study_id"] == "nbl_a"


@pytest.mark.anyio
async def test_lookup_genes_uses_hugo_symbols(client: Client, monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_request(method: str, path: str, **kwargs: object) -> list[dict[str, object]]:
        assert (method, path) == ("GET", "/genes")
        assert kwargs["params"] == {
            "keyword": "TP53",
            "pageNumber": 0,
            "pageSize": 100,
            "projection": "SUMMARY",
        }
        return [{"entrezGeneId": 7157, "hugoGeneSymbol": "TP53", "type": "protein-coding"}]

    monkeypatch.setattr(api, "request", fake_request)
    result = await client.call_tool("lookup_genes", {"symbols": ["tp53"]})

    assert result.structured_content["genes"][0]["entrez_gene_id"] == 7157


@pytest.mark.anyio
async def test_list_study_samples_returns_sample_ids(
    client: Client, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_request(method: str, path: str, **kwargs: object) -> list[dict[str, object]]:
        assert (method, path) == ("GET", "/studies/study_a/samples")
        assert kwargs["params"] == {"pageNumber": 0, "pageSize": 25, "projection": "SUMMARY"}
        return [{"sampleId": "sample-1", "patientId": "patient-1", "sampleType": "Primary"}]

    monkeypatch.setattr(api, "request", fake_request)
    result = await client.call_tool("list_study_samples", {"study_id": "study_a"})

    assert result.structured_content["samples"][0]["sample_id"] == "sample-1"


@pytest.mark.anyio
async def test_fetch_mutations_uses_bounded_filter(client: Client, monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_request(method: str, path: str, **kwargs: object) -> list[dict[str, object]]:
        assert (method, path) == ("POST", "/molecular-profiles/study_mutations/mutations/fetch")
        assert kwargs["params"] == {"projection": "SUMMARY"}
        assert kwargs["json"] == {"sampleIds": ["sample-1"], "entrezGeneIds": [7157]}
        return [{"sampleId": "sample-1", "entrezGeneId": 7157, "mutationType": "MISSENSE"}]

    monkeypatch.setattr(api, "request", fake_request)
    result = await client.call_tool(
        "fetch_mutations",
        {
            "molecular_profile_id": "study_mutations",
            "sample_ids": ["sample-1"],
            "entrez_gene_ids": [7157],
        },
    )

    assert result.structured_content["mutations"][0]["mutationType"] == "MISSENSE"


@pytest.mark.anyio
async def test_fetch_mutations_rejects_more_than_100_samples(client: Client) -> None:
    result = await client.call_tool(
        "fetch_mutations",
        {
            "molecular_profile_id": "study_mutations",
            "sample_ids": [f"sample-{index}" for index in range(101)],
            "entrez_gene_ids": [7157],
        },
    )

    assert result.is_error


@pytest.mark.anyio
async def test_find_patients_with_mutation_uses_sample_list_and_groups_patients(
    client: Client, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_request(method: str, path: str, **kwargs: object) -> list[dict[str, object]]:
        if (method, path) == ("GET", "/studies/study_a/molecular-profiles"):
            assert kwargs["params"] == {"projection": "SUMMARY"}
            return [{"molecularProfileId": "study_a_mutations", "molecularAlterationType": "MUTATION_EXTENDED"}]
        if (method, path) == ("GET", "/studies/study_a/sample-lists"):
            assert kwargs["params"] == {"projection": "SUMMARY"}
            return [{"sampleListId": "study_a_sequenced", "name": "Sequenced samples"}]
        if (method, path) == ("GET", "/genes"):
            assert kwargs["params"] == {
                "keyword": "BRAF",
                "pageNumber": 0,
                "pageSize": 100,
                "projection": "SUMMARY",
            }
            return [{"entrezGeneId": 673, "hugoGeneSymbol": "BRAF"}]
        if (method, path) == ("POST", "/molecular-profiles/study_a_mutations/mutations/fetch"):
            assert kwargs["json"] == {"sampleListId": "study_a_sequenced", "entrezGeneIds": [673]}
            return [
                {"patientId": "patient-1", "sampleId": "sample-1", "proteinChange": "p.V600E"},
                {"patientId": "patient-1", "sampleId": "sample-2", "proteinChange": "V600E"},
                {"patientId": "patient-2", "sampleId": "sample-3", "proteinChange": "V600K"},
            ]
        raise AssertionError(f"Unexpected request: {method} {path}")

    monkeypatch.setattr(api, "request", fake_request)
    result = await client.call_tool(
        "find_patients_with_mutation",
        {"study_id": "study_a", "gene_symbol": "braf", "protein_change": "V600E"},
    )

    assert result.structured_content["molecular_profile_id"] == "study_a_mutations"
    assert result.structured_content["patients"] == [
        {
            "patient_id": "patient-1",
            "sample_ids": ["sample-1", "sample-2"],
            "mutations": [
                {"patientId": "patient-1", "sampleId": "sample-1", "proteinChange": "p.V600E"},
                {"patientId": "patient-1", "sampleId": "sample-2", "proteinChange": "V600E"},
            ],
            "clinical_data": {},
        }
    ]


@pytest.mark.anyio
async def test_find_patients_with_mutation_fetches_requested_clinical_data(
    client: Client, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_request(method: str, path: str, **kwargs: object) -> list[dict[str, object]]:
        if path.endswith("/molecular-profiles"):
            return [{"molecularProfileId": "study_a_mutations", "molecularAlterationType": "MUTATION_EXTENDED"}]
        if path.endswith("/sample-lists"):
            return [{"sampleListId": "study_a_sequenced", "name": "Sequenced samples"}]
        if path == "/genes":
            return [{"entrezGeneId": 673, "hugoGeneSymbol": "BRAF"}]
        if path.endswith("/mutations/fetch"):
            return [{"patientId": "patient-1", "sampleId": "sample-1", "proteinChange": "V600E"}]
        if path == "/studies/study_a/clinical-data/fetch":
            assert kwargs["json"] == {"ids": ["patient-1"], "attributeIds": ["OS_STATUS"]}
            return [{"patientId": "patient-1", "clinicalAttributeId": "OS_STATUS", "value": "LIVING"}]
        raise AssertionError(f"Unexpected request: {method} {path}")

    monkeypatch.setattr(api, "request", fake_request)
    result = await client.call_tool(
        "find_patients_with_mutation",
        {
            "study_id": "study_a",
            "gene_symbol": "BRAF",
            "protein_change": "V600E",
            "clinical_attribute_ids": ["OS_STATUS"],
        },
    )

    assert result.structured_content["patients"][0]["clinical_data"] == {"OS_STATUS": "LIVING"}


@pytest.mark.anyio
async def test_assess_mutation_survival_compares_mutation_carriers(
    client: Client, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_request(method: str, path: str, **kwargs: object) -> list[dict[str, object]]:
        if path == "/studies/study_a/clinical-attributes":
            return [
                {"clinicalAttributeId": "OS_MONTHS"},
                {"clinicalAttributeId": "OS_STATUS"},
            ]
        if path == "/studies/study_a/patients":
            return [{"patientId": f"patient-{index}"} for index in range(1, 5)]
        if path.endswith("/molecular-profiles"):
            return [{"molecularProfileId": "study_a_mutations", "molecularAlterationType": "MUTATION_EXTENDED"}]
        if path.endswith("/sample-lists"):
            return [{"sampleListId": "study_a_sequenced", "name": "Sequenced samples"}]
        if path == "/genes":
            return [{"entrezGeneId": 673, "hugoGeneSymbol": "BRAF"}]
        if path.endswith("/mutations/fetch"):
            return [
                {"patientId": "patient-1", "proteinChange": "V600E"},
                {"patientId": "patient-2", "proteinChange": "V600E"},
            ]
        if path == "/studies/study_a/clinical-data/fetch":
            assert kwargs["json"] == {
                "ids": ["patient-1", "patient-2", "patient-3", "patient-4"],
                "attributeIds": ["OS_MONTHS", "OS_STATUS"],
            }
            return [
                {"patientId": "patient-1", "clinicalAttributeId": "OS_MONTHS", "value": "10"},
                {"patientId": "patient-1", "clinicalAttributeId": "OS_STATUS", "value": "DECEASED"},
                {"patientId": "patient-2", "clinicalAttributeId": "OS_MONTHS", "value": "20"},
                {"patientId": "patient-2", "clinicalAttributeId": "OS_STATUS", "value": "LIVING"},
                {"patientId": "patient-3", "clinicalAttributeId": "OS_MONTHS", "value": "30"},
                {"patientId": "patient-3", "clinicalAttributeId": "OS_STATUS", "value": "DECEASED"},
                {"patientId": "patient-4", "clinicalAttributeId": "OS_MONTHS", "value": "40"},
                {"patientId": "patient-4", "clinicalAttributeId": "OS_STATUS", "value": "DECEASED"},
            ]
        raise AssertionError(f"Unexpected request: {method} {path}")

    monkeypatch.setattr(api, "request", fake_request)
    result = await client.call_tool(
        "assess_mutation_survival",
        {"study_id": "study_a", "gene_symbol": "BRAF", "protein_change": "p.V600E"},
    )

    assert result.structured_content["mutation_group"] == {
        "patient_count": 2,
        "event_count": 1,
        "median_months": None,
    }
    assert result.structured_content["comparison_group"]["patient_count"] == 2
    assert result.structured_content["mutation_patient_ids"] == ["patient-1", "patient-2"]
    assert result.structured_content["conclusion"] == "not_demonstrably_different"


@pytest.mark.anyio
async def test_assess_gene_mutation_survival_evaluates_sufficient_variants(
    client: Client, monkeypatch: pytest.MonkeyPatch
) -> None:
    patient_ids = [f"patient-{index}" for index in range(1, 13)]

    async def fake_request(method: str, path: str, **kwargs: object) -> list[dict[str, object]]:
        if path == "/studies/study_a/clinical-attributes":
            return [{"clinicalAttributeId": "OS_MONTHS"}, {"clinicalAttributeId": "OS_STATUS"}]
        if path == "/studies/study_a/patients":
            return [{"patientId": patient_id} for patient_id in patient_ids]
        if path.endswith("/molecular-profiles"):
            return [{"molecularProfileId": "study_a_mutations", "molecularAlterationType": "MUTATION_EXTENDED"}]
        if path.endswith("/sample-lists"):
            return [{"sampleListId": "study_a_sequenced", "name": "Sequenced samples"}]
        if path == "/genes":
            return [{"entrezGeneId": 673, "hugoGeneSymbol": "BRAF"}]
        if path.endswith("/mutations/fetch"):
            return [
                {"patientId": "patient-1", "proteinChange": "V600E"},
                {"patientId": "patient-2", "proteinChange": "V600E"},
                {"patientId": "patient-3", "proteinChange": "V600K"},
                {"patientId": "patient-4", "proteinChange": "V600K"},
                {"patientId": "patient-5", "proteinChange": "V600K"},
                {"patientId": "patient-6", "proteinChange": "V600K"},
                {"patientId": "patient-7", "proteinChange": "V600K"},
            ]
        if path == "/studies/study_a/clinical-data/fetch":
            assert kwargs["json"] == {
                "ids": patient_ids,
                "attributeIds": ["OS_MONTHS", "OS_STATUS"],
            }
            return [
                clinical_value
                for index, patient_id in enumerate(patient_ids, start=1)
                for clinical_value in (
                    {
                        "patientId": patient_id,
                        "clinicalAttributeId": "OS_MONTHS",
                        "value": str(index * 10),
                    },
                    {
                        "patientId": patient_id,
                        "clinicalAttributeId": "OS_STATUS",
                        "value": "DECEASED" if index % 2 else "LIVING",
                    },
                )
            ]
        raise AssertionError(f"Unexpected request: {method} {path}")

    monkeypatch.setattr(api, "request", fake_request)
    result = await client.call_tool(
        "assess_gene_mutation_survival", {"study_id": "study_a", "gene_symbol": "BRAF"}
    )

    assert result.structured_content["analysis_mode"] == "per_mutation"
    assert result.structured_content["minimum_group_size"] == 5
    assert result.structured_content["analyses"][0]["protein_change"] == "V600K"
    assert result.structured_content["analyses"][0]["mutation_group"]["patient_count"] == 5
    assert result.structured_content["analyses"][0]["comparison_group"]["patient_count"] == 5


@pytest.mark.anyio
async def test_assess_gene_mutation_survival_falls_back_to_all_mutated_patients(
    client: Client, monkeypatch: pytest.MonkeyPatch
) -> None:
    patient_ids = [f"patient-{index}" for index in range(1, 12)]

    async def fake_request(method: str, path: str, **_kwargs: object) -> list[dict[str, object]]:
        del method, _kwargs
        if path == "/studies/study_a/clinical-attributes":
            return [{"clinicalAttributeId": "OS_MONTHS"}, {"clinicalAttributeId": "OS_STATUS"}]
        if path == "/studies/study_a/patients":
            return [{"patientId": patient_id} for patient_id in patient_ids]
        if path.endswith("/molecular-profiles"):
            return [{"molecularProfileId": "study_a_mutations", "molecularAlterationType": "MUTATION_EXTENDED"}]
        if path.endswith("/sample-lists"):
            return [{"sampleListId": "study_a_sequenced", "name": "Sequenced samples"}]
        if path == "/genes":
            return [{"entrezGeneId": 673, "hugoGeneSymbol": "BRAF"}]
        if path.endswith("/mutations/fetch"):
            return [
                {"patientId": "patient-1", "proteinChange": "V600E"},
                {"patientId": "patient-2", "proteinChange": "V600E"},
                {"patientId": "patient-3", "proteinChange": "V600K"},
                {"patientId": "patient-4", "proteinChange": "V600K"},
                {"patientId": "patient-5", "proteinChange": "V600K"},
            ]
        if path == "/studies/study_a/clinical-data/fetch":
            return [
                clinical_value
                for index, patient_id in enumerate(patient_ids, start=1)
                for clinical_value in (
                    {
                        "patientId": patient_id,
                        "clinicalAttributeId": "OS_MONTHS",
                        "value": str(index * 10),
                    },
                    {"patientId": patient_id, "clinicalAttributeId": "OS_STATUS", "value": "LIVING"},
                )
            ]
        raise AssertionError(f"Unexpected request: {method} {path}")

    monkeypatch.setattr(api, "request", fake_request)
    result = await client.call_tool(
        "assess_gene_mutation_survival", {"study_id": "study_a", "gene_symbol": "BRAF"}
    )

    assert result.structured_content["analysis_mode"] == "aggregated_mutated"
    assert result.structured_content["analyses"][0]["protein_change"] == "all_mutations"
    assert result.structured_content["analyses"][0]["mutation_group"]["patient_count"] == 5
    assert result.structured_content["analyses"][0]["comparison_group"]["patient_count"] == 6


@pytest.mark.anyio
async def test_single_request_wrappers_are_not_exposed(client: Client) -> None:
    tool_names = {tool.name for tool in (await client.list_tools()).tools}

    assert {"list_studies", "search_studies", "list_study_samples", "fetch_mutations"}.isdisjoint(
        tool_names
    )
