"""cBioPortal query orchestration independent of MCP registration."""

import asyncio
from typing import Any
from urllib.parse import quote

from mcp.server.mcpserver.exceptions import ToolError

from . import api
from .models import (
    Gene,
    GeneLookup,
    MolecularProfile,
    PatientMutation,
    PatientMutationCohort,
    Sample,
    SampleList,
    SampleListPage,
    Study,
    StudyAlterationResult,
    StudyDataCatalog,
)

MAX_COHORT_MUTATIONS = 10_000_000


def study_from_api(raw: dict[str, Any]) -> Study:
    return Study(
        study_id=raw["studyId"],
        name=raw.get("name", raw["studyId"]),
        description=raw.get("description"),
        cancer_type_id=raw.get("cancerTypeId"),
        sample_count=raw.get("allSampleCount"),
        reference_genome=raw.get("referenceGenome"),
    )


async def get_study_data_catalog(study_id: str) -> StudyDataCatalog:
    encoded_study_id = quote(study_id, safe="")
    study_data, profiles, sample_lists = await asyncio.gather(
        api.request("GET", f"/studies/{encoded_study_id}", params={"projection": "SUMMARY"}),
        api.request(
            "GET", f"/studies/{encoded_study_id}/molecular-profiles", params={"projection": "SUMMARY"}
        ),
        api.request("GET", f"/studies/{encoded_study_id}/sample-lists", params={"projection": "SUMMARY"}),
    )
    return StudyDataCatalog(
        study=study_from_api(study_data),
        molecular_profiles=[
            MolecularProfile(
                molecular_profile_id=item["molecularProfileId"],
                name=item.get("name", item["molecularProfileId"]),
                molecular_alteration_type=item["molecularAlterationType"],
                datatype=item["datatype"],
                description=item.get("description"),
            )
            for item in profiles
        ],
        sample_lists=[
            SampleList(
                sample_list_id=item["sampleListId"],
                name=item.get("name", item["sampleListId"]),
                description=item.get("description"),
                sample_count=item.get("sampleCount"),
            )
            for item in sample_lists
        ],
    )


async def list_study_samples(study_id: str, page_number: int, page_size: int) -> SampleListPage:
    data = await api.request(
        "GET",
        f"/studies/{quote(study_id, safe='')}/samples",
        params={"pageNumber": page_number, "pageSize": page_size, "projection": "SUMMARY"},
    )
    return SampleListPage(
        study_id=study_id,
        page_number=page_number,
        page_size=page_size,
        samples=[
            Sample(
                sample_id=item["sampleId"],
                patient_id=item["patientId"],
                sample_type=item.get("sampleType"),
            )
            for item in data
        ],
    )


async def lookup_genes(symbols: list[str]) -> GeneLookup:
    normalized_symbols = [symbol.strip().upper() for symbol in symbols]

    async def lookup(symbol: str) -> list[dict[str, Any]]:
        matches = await api.request(
            "GET",
            "/genes",
            params={"keyword": symbol, "pageNumber": 0, "pageSize": 100, "projection": "SUMMARY"},
        )
        return [item for item in matches if item.get("hugoGeneSymbol", "").upper() == symbol]

    matches_by_symbol = await asyncio.gather(*(lookup(symbol) for symbol in dict.fromkeys(normalized_symbols)))
    data = [item for matches in matches_by_symbol for item in matches]
    return GeneLookup(
        requested_symbols=normalized_symbols,
        genes=[
            Gene(
                entrez_gene_id=item["entrezGeneId"],
                hugo_gene_symbol=item["hugoGeneSymbol"],
                gene_type=item.get("type"),
            )
            for item in data
        ],
    )


async def mutation_profile_and_sample_list(study_id: str) -> tuple[str | None, str | None]:
    encoded_study_id = quote(study_id, safe="")
    profiles, sample_lists = await asyncio.gather(
        api.request(
            "GET", f"/studies/{encoded_study_id}/molecular-profiles", params={"projection": "SUMMARY"}
        ),
        api.request("GET", f"/studies/{encoded_study_id}/sample-lists", params={"projection": "SUMMARY"}),
    )
    profile_id = next(
        (
            item["molecularProfileId"]
            for item in profiles
            if item.get("molecularAlterationType") == "MUTATION_EXTENDED"
        ),
        None,
    )
    sample_list_id = next(
        (
            item["sampleListId"]
            for item in sample_lists
            if "mutation" in f"{item.get('name', '')} {item.get('description', '')}".lower()
            or item.get("sampleListId", "").endswith("_sequenced")
        ),
        None,
    )
    return profile_id, sample_list_id


async def mutation_profile_and_samples(study_id: str) -> tuple[Study, str | None, str | None]:
    catalog = await get_study_data_catalog(study_id)
    profile_id = next(
        (
            item.molecular_profile_id
            for item in catalog.molecular_profiles
            if item.molecular_alteration_type == "MUTATION_EXTENDED"
        ),
        None,
    )
    sample_list_id = next(
        (
            item.sample_list_id
            for item in catalog.sample_lists
            if "mutation" in f"{item.name} {item.description or ''}".lower()
            or item.sample_list_id.endswith("_sequenced")
        ),
        None,
    )
    return catalog.study, profile_id, sample_list_id


def normalized_protein_change(value: str) -> str:
    return value.strip().casefold().removeprefix("p.")


async def find_patients_with_mutation(
    study_id: str,
    gene_symbol: str,
    protein_change: str,
    clinical_attribute_ids: list[str] | None,
) -> PatientMutationCohort:
    normalized_symbol = gene_symbol.strip().upper()
    normalized_change = normalized_protein_change(protein_change)
    if not normalized_symbol or not normalized_change:
        raise ToolError("gene_symbol and protein_change must contain non-whitespace text.")

    (profile_id, sample_list_id), genes = await asyncio.gather(
        mutation_profile_and_sample_list(study_id),
        lookup_genes([normalized_symbol]),
    )
    if profile_id is None or sample_list_id is None:
        raise ToolError(f"Study '{study_id}' has no public mutation profile with a sequenced sample list.")
    if not genes.genes:
        raise ToolError(
            f"cBioPortal did not find Hugo gene symbol '{normalized_symbol}'. Check the symbol and retry."
        )

    gene = genes.genes[0]
    mutations = await api.request(
        "POST",
        f"/molecular-profiles/{quote(profile_id, safe='')}/mutations/fetch",
        params={"projection": "SUMMARY", "pageNumber": 0, "pageSize": MAX_COHORT_MUTATIONS},
        json={"sampleListId": sample_list_id, "entrezGeneIds": [gene.entrez_gene_id]},
    )
    mutations_by_patient: dict[str, list[dict[str, Any]]] = {}
    sample_ids_by_patient: dict[str, set[str]] = {}
    for mutation in mutations:
        if normalized_protein_change(str(mutation.get("proteinChange", ""))) != normalized_change:
            continue
        patient_id = mutation["patientId"]
        mutations_by_patient.setdefault(patient_id, []).append(mutation)
        sample_ids_by_patient.setdefault(patient_id, set()).add(mutation["sampleId"])

    clinical_data_by_patient: dict[str, dict[str, Any]] = {}
    if clinical_attribute_ids and mutations_by_patient:
        clinical_data = await api.request(
            "POST",
            f"/studies/{quote(study_id, safe='')}/clinical-data/fetch",
            params={"clinicalDataType": "PATIENT", "projection": "SUMMARY"},
            json={
                "ids": list(mutations_by_patient),
                "attributeIds": list(dict.fromkeys(clinical_attribute_ids)),
            },
        )
        for item in clinical_data:
            clinical_data_by_patient.setdefault(item["patientId"], {})[item["clinicalAttributeId"]] = item.get(
                "value"
            )

    return PatientMutationCohort(
        study_id=study_id,
        molecular_profile_id=profile_id,
        sample_list_id=sample_list_id,
        gene=gene,
        protein_change=protein_change.strip(),
        patients=[
            PatientMutation(
                patient_id=patient_id,
                sample_ids=sorted(sample_ids_by_patient[patient_id]),
                mutations=patient_mutations,
                clinical_data=clinical_data_by_patient.get(patient_id, {}),
            )
            for patient_id, patient_mutations in mutations_by_patient.items()
        ],
    )
