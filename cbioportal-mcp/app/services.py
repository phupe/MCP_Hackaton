"""cBioPortal query orchestration independent of MCP registration."""

import asyncio
import math
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
    GeneMutationSurvivalAnalysis,
    MutationSurvivalAnalysis,
    SurvivalGroup,
)

MAX_COHORT_MUTATIONS = 10_000_000
MAX_SURVIVAL_PATIENTS = 100_000
MIN_SURVIVAL_GROUP_SIZE = 5


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


def _survival_group(records: list[tuple[float, bool]]) -> SurvivalGroup:
    if not records:
        return SurvivalGroup(patient_count=0, event_count=0)
    ordered = sorted(records)
    at_risk = len(ordered)
    survival = 1.0
    median: float | None = None
    for time, event in ordered:
        if event:
            survival *= (at_risk - 1) / at_risk
            if median is None and survival <= 0.5:
                median = time
        at_risk -= 1
    return SurvivalGroup(
        patient_count=len(records),
        event_count=sum(event for _, event in records),
        median_months=median,
    )


def _log_rank(
    mutation_records: list[tuple[float, bool]], comparison_records: list[tuple[float, bool]]
) -> tuple[float | None, float | None]:
    if not mutation_records or not comparison_records:
        return None, None
    statistic = 0.0
    event_times = sorted({time for time, event in mutation_records + comparison_records if event})
    for time in event_times:
        at_risk_mutation = sum(record_time >= time for record_time, _ in mutation_records)
        at_risk_comparison = sum(record_time >= time for record_time, _ in comparison_records)
        at_risk = at_risk_mutation + at_risk_comparison
        events_mutation = sum(record_time == time and event for record_time, event in mutation_records)
        events_total = events_mutation + sum(
            record_time == time and event for record_time, event in comparison_records
        )
        if at_risk <= 1 or events_total == 0:
            continue
        expected = events_total * at_risk_mutation / at_risk
        variance = (
            at_risk_mutation
            * at_risk_comparison
            * events_total
            * (at_risk - events_total)
            / (at_risk * at_risk * (at_risk - 1))
        )
        if variance:
            statistic += (events_mutation - expected) ** 2 / variance
    return statistic, math.erfc(math.sqrt(statistic / 2))


def _clinical_attribute_id(attributes: list[dict[str, Any]], candidates: set[str]) -> str | None:
    for attribute in attributes:
        attribute_id = str(attribute.get("clinicalAttributeId", ""))
        if attribute_id.casefold() in candidates:
            return attribute_id
    return None


def _survival_conclusion(
    mutation_group: SurvivalGroup, comparison_group: SurvivalGroup, p_value: float | None
) -> str:
    if p_value is not None and p_value < 0.05:
        if (
            mutation_group.median_months is not None
            and comparison_group.median_months is not None
            and mutation_group.median_months > comparison_group.median_months
        ):
            return "better"
        if (
            mutation_group.median_months is not None
            and comparison_group.median_months is not None
            and mutation_group.median_months < comparison_group.median_months
        ):
            return "worse"
        return "different_but_medians_unavailable"
    return "not_demonstrably_different"


async def assess_mutation_survival(
    study_id: str, gene_symbol: str, protein_change: str
) -> MutationSurvivalAnalysis:
    attributes, patients, (profile_id, sample_list_id), genes = await asyncio.gather(
        api.request(
            "GET",
            f"/studies/{quote(study_id, safe='')}/clinical-attributes",
            params={"projection": "SUMMARY"},
        ),
        api.request(
            "GET",
            f"/studies/{quote(study_id, safe='')}/patients",
            params={"pageNumber": 0, "pageSize": MAX_SURVIVAL_PATIENTS, "projection": "SUMMARY"},
        ),
        mutation_profile_and_sample_list(study_id),
        lookup_genes([gene_symbol]),
    )
    time_attribute = _clinical_attribute_id(attributes, {"os_months", "overall_survival_months"})
    status_attribute = _clinical_attribute_id(attributes, {"os_status", "overall_survival_status"})
    if time_attribute is None or status_attribute is None:
        raise ToolError(
            f"Study '{study_id}' does not expose both OS_MONTHS and OS_STATUS survival attributes."
        )
    if profile_id is None or sample_list_id is None or not genes.genes:
        raise ToolError(f"Study '{study_id}' has no usable mutation profile or gene.")

    mutations = await api.request(
        "POST",
        f"/molecular-profiles/{quote(profile_id, safe='')}/mutations/fetch",
        params={"projection": "SUMMARY", "pageNumber": 0, "pageSize": MAX_COHORT_MUTATIONS},
        json={"sampleListId": sample_list_id, "entrezGeneIds": [genes.genes[0].entrez_gene_id]},
    )
    normalized_change = normalized_protein_change(protein_change)
    mutation_patient_ids = {
        str(item["patientId"])
        for item in mutations
        if normalized_protein_change(str(item.get("proteinChange", ""))) == normalized_change
    }
    patient_ids = [str(item["patientId"]) for item in patients]
    clinical_data = await api.request(
        "POST",
        f"/studies/{quote(study_id, safe='')}/clinical-data/fetch",
        params={"clinicalDataType": "PATIENT", "projection": "SUMMARY"},
        json={
            "ids": patient_ids,
            "attributeIds": [time_attribute, status_attribute],
        },
    )
    values: dict[str, dict[str, str]] = {}
    for item in clinical_data:
        values.setdefault(str(item["patientId"]), {})[str(item["clinicalAttributeId"])] = str(
            item.get("value", "")
        )
    mutation_records: list[tuple[float, bool]] = []
    comparison_records: list[tuple[float, bool]] = []
    for patient_id in patient_ids:
        patient_values = values.get(patient_id, {})
        try:
            time = float(patient_values[time_attribute])
        except (KeyError, TypeError, ValueError):
            continue
        status = patient_values.get(status_attribute, "").casefold()
        event = status in {"deceased", "dead", "1", "yes", "true"}
        (mutation_records if patient_id in mutation_patient_ids else comparison_records).append((time, event))

    mutation_group = _survival_group(mutation_records)
    comparison_group = _survival_group(comparison_records)
    statistic, p_value = _log_rank(mutation_records, comparison_records)
    return MutationSurvivalAnalysis(
        study_id=study_id,
        gene_symbol=genes.genes[0].hugo_gene_symbol,
        protein_change=protein_change.strip(),
        survival_time_attribute=time_attribute,
        survival_status_attribute=status_attribute,
        mutation_group=mutation_group,
        comparison_group=comparison_group,
        log_rank_statistic=statistic,
        log_rank_p_value=p_value,
        conclusion=_survival_conclusion(mutation_group, comparison_group, p_value),
        mutation_patient_ids=sorted(mutation_patient_ids),
    )


async def assess_gene_mutation_survival(study_id: str, gene_symbol: str) -> GeneMutationSurvivalAnalysis:
    """Assess each sufficiently represented protein mutation, or all mutated patients as a fallback."""
    attributes, patients, (profile_id, sample_list_id), genes = await asyncio.gather(
        api.request(
            "GET",
            f"/studies/{quote(study_id, safe='')}/clinical-attributes",
            params={"projection": "SUMMARY"},
        ),
        api.request(
            "GET",
            f"/studies/{quote(study_id, safe='')}/patients",
            params={"pageNumber": 0, "pageSize": MAX_SURVIVAL_PATIENTS, "projection": "SUMMARY"},
        ),
        mutation_profile_and_sample_list(study_id),
        lookup_genes([gene_symbol]),
    )
    time_attribute = _clinical_attribute_id(attributes, {"os_months", "overall_survival_months"})
    status_attribute = _clinical_attribute_id(attributes, {"os_status", "overall_survival_status"})
    if time_attribute is None or status_attribute is None:
        raise ToolError(
            f"Study '{study_id}' does not expose both OS_MONTHS and OS_STATUS survival attributes."
        )
    if profile_id is None or sample_list_id is None or not genes.genes:
        raise ToolError(f"Study '{study_id}' has no usable mutation profile or gene.")

    mutations = await api.request(
        "POST",
        f"/molecular-profiles/{quote(profile_id, safe='')}/mutations/fetch",
        params={"projection": "SUMMARY", "pageNumber": 0, "pageSize": MAX_COHORT_MUTATIONS},
        json={"sampleListId": sample_list_id, "entrezGeneIds": [genes.genes[0].entrez_gene_id]},
    )
    patient_ids = [str(item["patientId"]) for item in patients]
    clinical_data = await api.request(
        "POST",
        f"/studies/{quote(study_id, safe='')}/clinical-data/fetch",
        params={"clinicalDataType": "PATIENT", "projection": "SUMMARY"},
        json={"ids": patient_ids, "attributeIds": [time_attribute, status_attribute]},
    )
    values: dict[str, dict[str, str]] = {}
    for item in clinical_data:
        values.setdefault(str(item["patientId"]), {})[str(item["clinicalAttributeId"])] = str(
            item.get("value", "")
        )
    records_by_patient: dict[str, tuple[float, bool]] = {}
    for patient_id in patient_ids:
        patient_values = values.get(patient_id, {})
        try:
            time = float(patient_values[time_attribute])
        except (KeyError, TypeError, ValueError):
            continue
        status = patient_values.get(status_attribute, "").casefold()
        records_by_patient[patient_id] = (time, status in {"deceased", "dead", "1", "yes", "true"})

    mutation_patients: dict[str, set[str]] = {}
    all_mutated_patient_ids: set[str] = set()
    for mutation in mutations:
        patient_id = str(mutation.get("patientId", ""))
        if patient_id not in records_by_patient:
            continue
        all_mutated_patient_ids.add(patient_id)
        protein_change = normalized_protein_change(str(mutation.get("proteinChange", "")))
        if protein_change:
            mutation_patients.setdefault(protein_change, set()).add(patient_id)

    wild_type_records = [
        record for patient_id, record in records_by_patient.items() if patient_id not in all_mutated_patient_ids
    ]

    def analysis_for(protein_change: str, mutation_patient_ids: set[str]) -> MutationSurvivalAnalysis:
        mutation_records = [records_by_patient[patient_id] for patient_id in sorted(mutation_patient_ids)]
        mutation_group = _survival_group(mutation_records)
        comparison_group = _survival_group(wild_type_records)
        statistic, p_value = _log_rank(mutation_records, wild_type_records)
        return MutationSurvivalAnalysis(
            study_id=study_id,
            gene_symbol=genes.genes[0].hugo_gene_symbol,
            protein_change=protein_change,
            survival_time_attribute=time_attribute,
            survival_status_attribute=status_attribute,
            mutation_group=mutation_group,
            comparison_group=comparison_group,
            log_rank_statistic=statistic,
            log_rank_p_value=p_value,
            conclusion=_survival_conclusion(mutation_group, comparison_group, p_value),
            mutation_patient_ids=sorted(mutation_patient_ids),
        )

    analyses = [
        analysis_for(protein_change.upper(), mutation_patient_ids)
        for protein_change, mutation_patient_ids in sorted(mutation_patients.items())
        if len(mutation_patient_ids) >= MIN_SURVIVAL_GROUP_SIZE
        and len(wild_type_records) >= MIN_SURVIVAL_GROUP_SIZE
    ]
    if analyses:
        return GeneMutationSurvivalAnalysis(
            study_id=study_id,
            gene_symbol=genes.genes[0].hugo_gene_symbol,
            survival_time_attribute=time_attribute,
            survival_status_attribute=status_attribute,
            minimum_group_size=MIN_SURVIVAL_GROUP_SIZE,
            analysis_mode="per_mutation",
            analyses=analyses,
        )

    if (
        len(all_mutated_patient_ids) < MIN_SURVIVAL_GROUP_SIZE
        or len(wild_type_records) < MIN_SURVIVAL_GROUP_SIZE
    ):
        raise ToolError(
            f"Study '{study_id}' has fewer than {MIN_SURVIVAL_GROUP_SIZE} patients with survival data "
            "in either the mutated or non-mutated group for this gene."
        )
    return GeneMutationSurvivalAnalysis(
        study_id=study_id,
        gene_symbol=genes.genes[0].hugo_gene_symbol,
        survival_time_attribute=time_attribute,
        survival_status_attribute=status_attribute,
        minimum_group_size=MIN_SURVIVAL_GROUP_SIZE,
        analysis_mode="aggregated_mutated",
        analyses=[analysis_for("all_mutations", all_mutated_patient_ids)],
    )
