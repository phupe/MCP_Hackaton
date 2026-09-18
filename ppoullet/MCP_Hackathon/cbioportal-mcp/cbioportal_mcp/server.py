"""MCP server exposing the cBioPortal REST API as tools.

API docs: https://docs.cbioportal.org/web-api-and-clients/
Swagger:  https://www.cbioportal.org/api/swagger-ui/index.html

By default this talks to the public instance at https://www.cbioportal.org/api.
Point it at a different instance (e.g. an institutional one) by setting the
CBIOPORTAL_API_URL environment variable, and CBIOPORTAL_API_TOKEN if it
requires a bearer token.

Almost every "list"/"get" endpoint in the cBioPortal API supports paging and
a `projection` level of detail. Projection is one of:
  - ID       : identifiers only
  - SUMMARY  : identifiers + commonly used fields (default here)
  - DETAILED : SUMMARY + nested related objects
  - META     : SUMMARY + a total row/result count
"""

from __future__ import annotations

from typing import Any, Literal

from mcp.server.fastmcp import FastMCP

from cbioportal_mcp.client import CBioPortalClient
from cbioportal_mcp.models import (
    ClinicalDataIdentifier,
    PatientIdentifier,
    SampleIdentifier,
    SampleMolecularIdentifier,
)

Projection = Literal["ID", "SUMMARY", "DETAILED", "META"]
Direction = Literal["ASC", "DESC"]
ClinicalDataType = Literal["SAMPLE", "PATIENT"]

mcp = FastMCP(
    name="cbioportal",
    instructions=(
        "Query cBioPortal (https://www.cbioportal.org), a public repository of cancer genomics "
        "study data: studies, patients, samples, clinical attributes, mutations, copy-number "
        "alterations, expression/other molecular data, gene panels and treatments. Start with "
        "list_studies / search_genes to discover IDs, then use the more specific fetch_* tools."
    ),
)

client = CBioPortalClient()


def _paging(page_number: int, page_size: int, sort_by: str | None, direction: Direction) -> dict[str, Any]:
    return {"pageNumber": page_number, "pageSize": page_size, "sortBy": sort_by, "direction": direction}


# --------------------------------------------------------------------------
# General
# --------------------------------------------------------------------------


@mcp.tool()
async def get_api_info() -> Any:
    """Get metadata about the running cBioPortal instance (portal version, DB version, git commit)."""
    return await client.get("/info")


@mcp.tool()
async def get_api_health() -> Any:
    """Check whether the cBioPortal API server and its database connection are up."""
    return await client.get("/health")


# --------------------------------------------------------------------------
# Cancer types
# --------------------------------------------------------------------------


@mcp.tool()
async def list_cancer_types(
    page_number: int = 0,
    page_size: int = 100,
    sort_by: str | None = None,
    direction: Direction = "ASC",
    projection: Projection = "SUMMARY",
) -> Any:
    """List cancer types known to cBioPortal (e.g. 'brca', 'luad'), with their display names and parent type."""
    return await client.get("/cancer-types", {**_paging(page_number, page_size, sort_by, direction), "projection": projection})


@mcp.tool()
async def get_cancer_type(cancer_type_id: str) -> Any:
    """Get a single cancer type by its ID, e.g. 'brca'."""
    return await client.get(f"/cancer-types/{cancer_type_id}")


# --------------------------------------------------------------------------
# Studies
# --------------------------------------------------------------------------


@mcp.tool()
async def list_studies(
    keyword: str | None = None,
    page_number: int = 0,
    page_size: int = 50,
    sort_by: str | None = None,
    direction: Direction = "ASC",
    projection: Projection = "SUMMARY",
) -> Any:
    """List/search cancer studies. `keyword` matches against study name and cancer type
    (e.g. 'breast', 'TCGA', 'pancreatic'). Returns study IDs (e.g. 'acc_tcga') used by most other tools."""
    return await client.get(
        "/studies",
        {**_paging(page_number, page_size, sort_by, direction), "keyword": keyword, "projection": projection},
    )


@mcp.tool()
async def get_study(study_id: str) -> Any:
    """Get details of one cancer study by its ID, e.g. 'acc_tcga'."""
    return await client.get(f"/studies/{study_id}")


@mcp.tool()
async def fetch_studies(study_ids: list[str], projection: Projection = "SUMMARY") -> Any:
    """Get details for several studies at once by ID."""
    return await client.post("/studies/fetch", study_ids, {"projection": projection})


@mcp.tool()
async def get_study_tags(study_id: str) -> Any:
    """Get the descriptive tags/badges attached to a study (e.g. data types available)."""
    return await client.get(f"/studies/{study_id}/tags")


@mcp.tool()
async def get_study_molecular_profiles(study_id: str, projection: Projection = "SUMMARY") -> Any:
    """List the molecular profiles (mutations, CNA, mRNA expression, etc.) available for a study."""
    return await client.get(f"/studies/{study_id}/molecular-profiles", {"projection": projection})


@mcp.tool()
async def get_study_sample_lists(study_id: str, projection: Projection = "SUMMARY") -> Any:
    """List the predefined sample lists (cohorts, e.g. 'all samples', 'samples with mutation data') in a study."""
    return await client.get(f"/studies/{study_id}/sample-lists", {"projection": projection})


# --------------------------------------------------------------------------
# Samples
# --------------------------------------------------------------------------


@mcp.tool()
async def list_samples(
    keyword: str | None = None,
    page_number: int = 0,
    page_size: int = 50,
    sort_by: str | None = None,
    direction: Direction = "ASC",
    projection: Projection = "SUMMARY",
) -> Any:
    """Search samples across all studies by keyword (matches sample/study identifiers)."""
    return await client.get(
        "/samples",
        {**_paging(page_number, page_size, sort_by, direction), "keyword": keyword, "projection": projection},
    )


@mcp.tool()
async def get_study_samples(
    study_id: str,
    page_number: int = 0,
    page_size: int = 100,
    sort_by: str | None = None,
    direction: Direction = "ASC",
    projection: Projection = "SUMMARY",
) -> Any:
    """List all samples in a study."""
    return await client.get(
        f"/studies/{study_id}/samples",
        {**_paging(page_number, page_size, sort_by, direction), "projection": projection},
    )


@mcp.tool()
async def get_sample(study_id: str, sample_id: str) -> Any:
    """Get one sample's details (e.g. sample type, patient ID) within a study."""
    return await client.get(f"/studies/{study_id}/samples/{sample_id}")


@mcp.tool()
async def fetch_samples(
    sample_identifiers: list[SampleIdentifier] | None = None,
    sample_list_ids: list[str] | None = None,
    projection: Projection = "SUMMARY",
) -> Any:
    """Fetch samples by (studyId, sampleId) pairs and/or by sample list IDs. Provide at least one of the two."""
    body: dict[str, Any] = {}
    if sample_identifiers:
        body["sampleIdentifiers"] = [s.model_dump() for s in sample_identifiers]
    if sample_list_ids:
        body["sampleListIds"] = sample_list_ids
    return await client.post("/samples/fetch", body, {"projection": projection})


@mcp.tool()
async def list_sample_lists(
    page_number: int = 0,
    page_size: int = 50,
    sort_by: str | None = None,
    direction: Direction = "ASC",
    projection: Projection = "SUMMARY",
) -> Any:
    """List predefined sample lists (cohorts) across all studies."""
    return await client.get("/sample-lists", {**_paging(page_number, page_size, sort_by, direction), "projection": projection})


@mcp.tool()
async def get_sample_list(sample_list_id: str) -> Any:
    """Get details of a sample list, e.g. 'acc_tcga_all'."""
    return await client.get(f"/sample-lists/{sample_list_id}")


@mcp.tool()
async def get_sample_list_sample_ids(sample_list_id: str) -> Any:
    """Get the plain list of sample IDs contained in a sample list, e.g. 'acc_tcga_all'."""
    return await client.get(f"/sample-lists/{sample_list_id}/sample-ids")


@mcp.tool()
async def fetch_sample_lists(sample_list_ids: list[str], projection: Projection = "SUMMARY") -> Any:
    """Fetch details for several sample lists at once by ID."""
    return await client.post("/sample-lists/fetch", sample_list_ids, {"projection": projection})


# --------------------------------------------------------------------------
# Patients
# --------------------------------------------------------------------------


@mcp.tool()
async def list_patients(
    keyword: str | None = None,
    page_number: int = 0,
    page_size: int = 50,
    sort_by: str | None = None,
    direction: Direction = "ASC",
    projection: Projection = "SUMMARY",
) -> Any:
    """Search patients across all studies by keyword (matches patient ID)."""
    return await client.get(
        "/patients",
        {**_paging(page_number, page_size, sort_by, direction), "keyword": keyword, "projection": projection},
    )


@mcp.tool()
async def get_study_patients(
    study_id: str,
    page_number: int = 0,
    page_size: int = 100,
    sort_by: str | None = None,
    direction: Direction = "ASC",
    projection: Projection = "SUMMARY",
) -> Any:
    """List all patients in a study."""
    return await client.get(
        f"/studies/{study_id}/patients",
        {**_paging(page_number, page_size, sort_by, direction), "projection": projection},
    )


@mcp.tool()
async def get_patient(study_id: str, patient_id: str) -> Any:
    """Get one patient's details within a study."""
    return await client.get(f"/studies/{study_id}/patients/{patient_id}")


@mcp.tool()
async def get_patient_samples(study_id: str, patient_id: str, projection: Projection = "SUMMARY") -> Any:
    """List all samples belonging to one patient in a study."""
    return await client.get(f"/studies/{study_id}/patients/{patient_id}/samples", {"projection": projection})


@mcp.tool()
async def fetch_patients(patient_identifiers: list[PatientIdentifier], projection: Projection = "SUMMARY") -> Any:
    """Fetch patient details for a list of (studyId, patientId) pairs, possibly across several studies."""
    body = {"patientIdentifiers": [p.model_dump() for p in patient_identifiers]}
    return await client.post("/patients/fetch", body, {"projection": projection})


# --------------------------------------------------------------------------
# Clinical attributes & clinical data
# --------------------------------------------------------------------------


@mcp.tool()
async def list_clinical_attributes(
    page_number: int = 0,
    page_size: int = 100,
    sort_by: str | None = None,
    direction: Direction = "ASC",
    projection: Projection = "SUMMARY",
) -> Any:
    """List all clinical attribute definitions (e.g. AGE, SEX, CANCER_TYPE, OS_MONTHS) known across all studies."""
    return await client.get(
        "/clinical-attributes", {**_paging(page_number, page_size, sort_by, direction), "projection": projection}
    )


@mcp.tool()
async def fetch_clinical_attributes(study_ids: list[str], projection: Projection = "SUMMARY") -> Any:
    """List clinical attribute definitions available in a given set of studies."""
    return await client.post("/clinical-attributes/fetch", study_ids, {"projection": projection})


@mcp.tool()
async def get_study_clinical_attributes(
    study_id: str,
    page_number: int = 0,
    page_size: int = 200,
    sort_by: str | None = None,
    direction: Direction = "ASC",
    projection: Projection = "SUMMARY",
) -> Any:
    """List clinical attribute definitions (e.g. AGE, SEX, OS_MONTHS) available in one study."""
    return await client.get(
        f"/studies/{study_id}/clinical-attributes",
        {**_paging(page_number, page_size, sort_by, direction), "projection": projection},
    )


@mcp.tool()
async def get_study_clinical_attribute(study_id: str, clinical_attribute_id: str) -> Any:
    """Get one clinical attribute's definition (name, description, data type) within a study."""
    return await client.get(f"/studies/{study_id}/clinical-attributes/{clinical_attribute_id}")


@mcp.tool()
async def get_study_clinical_data(
    study_id: str,
    clinical_data_type: ClinicalDataType = "SAMPLE",
    attribute_id: str | None = None,
    page_number: int = 0,
    page_size: int = 500,
    sort_by: str | None = None,
    direction: Direction = "ASC",
    projection: Projection = "SUMMARY",
) -> Any:
    """Get clinical data values (e.g. AGE, SEX, tumor stage) for all samples/patients in a study.
    Set clinical_data_type to PATIENT for patient-level attributes (e.g. OS_MONTHS), or SAMPLE for
    sample-level ones (e.g. TUMOR_PURITY). Filter to one attribute with attribute_id."""
    return await client.get(
        f"/studies/{study_id}/clinical-data",
        {
            **_paging(page_number, page_size, sort_by, direction),
            "clinicalDataType": clinical_data_type,
            "attributeId": attribute_id,
            "projection": projection,
        },
    )


@mcp.tool()
async def get_sample_clinical_data(study_id: str, sample_id: str, projection: Projection = "SUMMARY") -> Any:
    """Get all clinical data values for one sample in a study."""
    return await client.get(f"/studies/{study_id}/samples/{sample_id}/clinical-data", {"projection": projection})


@mcp.tool()
async def get_patient_clinical_data(study_id: str, patient_id: str, projection: Projection = "SUMMARY") -> Any:
    """Get all clinical data values for one patient in a study."""
    return await client.get(f"/studies/{study_id}/patients/{patient_id}/clinical-data", {"projection": projection})


@mcp.tool()
async def fetch_study_clinical_data(
    study_id: str,
    ids: list[str],
    clinical_data_type: ClinicalDataType = "SAMPLE",
    attribute_ids: list[str] | None = None,
    projection: Projection = "SUMMARY",
) -> Any:
    """Fetch clinical data for specific sample IDs (or patient IDs, if clinical_data_type=PATIENT) within
    one study, optionally restricted to specific attribute_ids (e.g. ['AGE', 'SEX'])."""
    body: dict[str, Any] = {"ids": ids}
    if attribute_ids:
        body["attributeIds"] = attribute_ids
    return await client.post(
        f"/studies/{study_id}/clinical-data/fetch",
        body,
        {"clinicalDataType": clinical_data_type, "projection": projection},
    )


@mcp.tool()
async def fetch_clinical_data(
    identifiers: list[ClinicalDataIdentifier],
    clinical_data_type: ClinicalDataType = "SAMPLE",
    attribute_ids: list[str] | None = None,
    projection: Projection = "SUMMARY",
) -> Any:
    """Fetch clinical data across multiple studies at once, given explicit (studyId, entityId) pairs
    (entityId = sampleId or patientId depending on clinical_data_type), optionally restricted to
    specific attribute_ids."""
    body: dict[str, Any] = {"identifiers": [i.model_dump() for i in identifiers]}
    if attribute_ids:
        body["attributeIds"] = attribute_ids
    return await client.post(
        "/clinical-data/fetch", body, {"clinicalDataType": clinical_data_type, "projection": projection}
    )


# --------------------------------------------------------------------------
# Genes & gene panels
# --------------------------------------------------------------------------


@mcp.tool()
async def search_genes(
    keyword: str | None = None,
    alias: str | None = None,
    page_number: int = 0,
    page_size: int = 50,
    sort_by: str | None = None,
    direction: Direction = "ASC",
    projection: Projection = "SUMMARY",
) -> Any:
    """Search genes by Hugo symbol keyword (e.g. 'TP', matches TP53, TP63...) or by alias."""
    return await client.get(
        "/genes",
        {**_paging(page_number, page_size, sort_by, direction), "keyword": keyword, "alias": alias, "projection": projection},
    )


@mcp.tool()
async def get_gene(gene_id: str) -> Any:
    """Get one gene by Entrez Gene ID or Hugo Gene Symbol, e.g. '7157' or 'TP53'."""
    return await client.get(f"/genes/{gene_id}")


@mcp.tool()
async def get_gene_aliases(gene_id: str) -> Any:
    """Get known aliases for a gene, by Entrez Gene ID or Hugo Gene Symbol."""
    return await client.get(f"/genes/{gene_id}/aliases")


@mcp.tool()
async def fetch_genes(
    gene_ids: list[str],
    gene_id_type: Literal["ENTREZ_GENE_ID", "HUGO_GENE_SYMBOL"] = "HUGO_GENE_SYMBOL",
    projection: Projection = "SUMMARY",
) -> Any:
    """Fetch several genes at once, by Entrez Gene IDs or Hugo Gene Symbols (set gene_id_type accordingly)."""
    return await client.post("/genes/fetch", gene_ids, {"geneIdType": gene_id_type, "projection": projection})


@mcp.tool()
async def list_gene_panels(
    page_number: int = 0,
    page_size: int = 50,
    sort_by: str | None = None,
    direction: Direction = "ASC",
    projection: Projection = "SUMMARY",
) -> Any:
    """List targeted sequencing gene panels (e.g. 'IMPACT341') known to cBioPortal."""
    return await client.get("/gene-panels", {**_paging(page_number, page_size, sort_by, direction), "projection": projection})


@mcp.tool()
async def get_gene_panel(gene_panel_id: str) -> Any:
    """Get the list of genes in a gene panel, e.g. 'IMPACT341'."""
    return await client.get(f"/gene-panels/{gene_panel_id}")


@mcp.tool()
async def fetch_gene_panels(gene_panel_ids: list[str], projection: Projection = "SUMMARY") -> Any:
    """Fetch details for several gene panels at once by ID."""
    return await client.post("/gene-panels/fetch", gene_panel_ids, {"projection": projection})


@mcp.tool()
async def fetch_gene_panel_data(
    molecular_profile_id: str,
    sample_ids: list[str] | None = None,
    sample_list_id: str | None = None,
) -> Any:
    """Get which gene panel (if any) was used for each sample in one molecular profile, i.e. which
    genes were actually assayed per sample. Provide sample_ids or a sample_list_id."""
    body: dict[str, Any] = {}
    if sample_ids:
        body["sampleIds"] = sample_ids
    if sample_list_id:
        body["sampleListId"] = sample_list_id
    return await client.post(f"/molecular-profiles/{molecular_profile_id}/gene-panel-data/fetch", body)


@mcp.tool()
async def fetch_gene_panel_data_multi_study(
    molecular_profile_ids: list[str] | None = None,
    sample_molecular_identifiers: list[SampleMolecularIdentifier] | None = None,
) -> Any:
    """Get gene-panel-per-sample assignments across multiple molecular profiles/studies at once."""
    body: dict[str, Any] = {}
    if molecular_profile_ids:
        body["molecularProfileIds"] = molecular_profile_ids
    if sample_molecular_identifiers:
        body["sampleMolecularIdentifiers"] = [s.model_dump() for s in sample_molecular_identifiers]
    return await client.post("/gene-panel-data/fetch", body)


# --------------------------------------------------------------------------
# Molecular profiles
# --------------------------------------------------------------------------


@mcp.tool()
async def list_molecular_profiles(
    page_number: int = 0,
    page_size: int = 50,
    sort_by: str | None = None,
    direction: Direction = "ASC",
    projection: Projection = "SUMMARY",
) -> Any:
    """List molecular profiles (data types such as mutations, CNA, mRNA/protein expression) across all studies."""
    return await client.get(
        "/molecular-profiles", {**_paging(page_number, page_size, sort_by, direction), "projection": projection}
    )


@mcp.tool()
async def get_molecular_profile(molecular_profile_id: str) -> Any:
    """Get one molecular profile's details, e.g. 'acc_tcga_mutations' or 'acc_tcga_rna_seq_v2_mrna'."""
    return await client.get(f"/molecular-profiles/{molecular_profile_id}")


@mcp.tool()
async def fetch_molecular_profiles(
    study_ids: list[str] | None = None,
    molecular_profile_ids: list[str] | None = None,
    projection: Projection = "SUMMARY",
) -> Any:
    """Fetch molecular profiles by study_ids and/or by explicit molecular_profile_ids."""
    body: dict[str, Any] = {}
    if study_ids:
        body["studyIds"] = study_ids
    if molecular_profile_ids:
        body["molecularProfileIds"] = molecular_profile_ids
    return await client.post("/molecular-profiles/fetch", body, {"projection": projection})


# --------------------------------------------------------------------------
# Mutations
# --------------------------------------------------------------------------


@mcp.tool()
async def get_mutations_in_molecular_profile(
    molecular_profile_id: str,
    sample_list_id: str,
    entrez_gene_id: int | None = None,
    page_number: int = 0,
    page_size: int = 200,
    sort_by: str | None = None,
    direction: Direction = "ASC",
    projection: Projection = "DETAILED",
) -> Any:
    """Get mutations in a mutation molecular profile (e.g. 'acc_tcga_mutations') for a whole sample list
    (cohort), optionally filtered to one gene by entrez_gene_id."""
    return await client.get(
        f"/molecular-profiles/{molecular_profile_id}/mutations",
        {
            **_paging(page_number, page_size, sort_by, direction),
            "sampleListId": sample_list_id,
            "entrezGeneId": entrez_gene_id,
            "projection": projection,
        },
    )


@mcp.tool()
async def fetch_mutations_in_molecular_profile(
    molecular_profile_id: str,
    sample_ids: list[str] | None = None,
    sample_list_id: str | None = None,
    entrez_gene_ids: list[int] | None = None,
    page_number: int = 0,
    page_size: int = 200,
    sort_by: str | None = None,
    direction: Direction = "ASC",
    projection: Projection = "DETAILED",
) -> Any:
    """Fetch mutations in one molecular profile for specific sample_ids (or a sample_list_id) and,
    optionally, specific entrez_gene_ids. This is the most common way to ask 'what mutations do
    these samples have in gene X'."""
    body: dict[str, Any] = {}
    if sample_ids:
        body["sampleIds"] = sample_ids
    if sample_list_id:
        body["sampleListId"] = sample_list_id
    if entrez_gene_ids:
        body["entrezGeneIds"] = entrez_gene_ids
    return await client.post(
        f"/molecular-profiles/{molecular_profile_id}/mutations/fetch",
        body,
        {**_paging(page_number, page_size, sort_by, direction), "projection": projection},
    )


@mcp.tool()
async def fetch_mutations_multi_study(
    molecular_profile_ids: list[str] | None = None,
    sample_molecular_identifiers: list[SampleMolecularIdentifier] | None = None,
    entrez_gene_ids: list[int] | None = None,
    page_number: int = 0,
    page_size: int = 200,
    sort_by: str | None = None,
    direction: Direction = "ASC",
    projection: Projection = "DETAILED",
) -> Any:
    """Fetch mutations across several molecular profiles/studies at once. Provide either
    molecular_profile_ids (all samples in those profiles) or explicit sample_molecular_identifiers
    (specific sample+profile pairs), optionally restricted to entrez_gene_ids."""
    body: dict[str, Any] = {}
    if molecular_profile_ids:
        body["molecularProfileIds"] = molecular_profile_ids
    if sample_molecular_identifiers:
        body["sampleMolecularIdentifiers"] = [s.model_dump() for s in sample_molecular_identifiers]
    if entrez_gene_ids:
        body["entrezGeneIds"] = entrez_gene_ids
    return await client.post(
        "/mutations/fetch",
        body,
        {**_paging(page_number, page_size, sort_by, direction), "projection": projection},
    )


# --------------------------------------------------------------------------
# Molecular data (expression, protein, methylation, etc.)
# --------------------------------------------------------------------------


@mcp.tool()
async def get_molecular_data(
    molecular_profile_id: str,
    sample_list_id: str,
    entrez_gene_id: int,
    projection: Projection = "SUMMARY",
) -> Any:
    """Get molecular data values (e.g. mRNA expression z-scores) for one gene across a whole sample
    list (cohort) in a molecular profile such as 'acc_tcga_rna_seq_v2_mrna'."""
    return await client.get(
        f"/molecular-profiles/{molecular_profile_id}/molecular-data",
        {"sampleListId": sample_list_id, "entrezGeneId": entrez_gene_id, "projection": projection},
    )


@mcp.tool()
async def fetch_molecular_data(
    molecular_profile_id: str,
    sample_ids: list[str] | None = None,
    sample_list_id: str | None = None,
    entrez_gene_ids: list[int] | None = None,
    projection: Projection = "SUMMARY",
) -> Any:
    """Fetch molecular data (e.g. mRNA/protein expression, methylation) for specific sample_ids (or a
    sample_list_id) and, optionally, specific entrez_gene_ids, within one molecular profile."""
    body: dict[str, Any] = {}
    if sample_ids:
        body["sampleIds"] = sample_ids
    if sample_list_id:
        body["sampleListId"] = sample_list_id
    if entrez_gene_ids:
        body["entrezGeneIds"] = entrez_gene_ids
    return await client.post(
        f"/molecular-profiles/{molecular_profile_id}/molecular-data/fetch", body, {"projection": projection}
    )


@mcp.tool()
async def fetch_molecular_data_multi_study(
    molecular_profile_ids: list[str] | None = None,
    sample_molecular_identifiers: list[SampleMolecularIdentifier] | None = None,
    entrez_gene_ids: list[int] | None = None,
    projection: Projection = "SUMMARY",
) -> Any:
    """Fetch molecular data across several molecular profiles/studies at once."""
    body: dict[str, Any] = {}
    if molecular_profile_ids:
        body["molecularProfileIds"] = molecular_profile_ids
    if sample_molecular_identifiers:
        body["sampleMolecularIdentifiers"] = [s.model_dump() for s in sample_molecular_identifiers]
    if entrez_gene_ids:
        body["entrezGeneIds"] = entrez_gene_ids
    return await client.post("/molecular-data/fetch", body, {"projection": projection})


# --------------------------------------------------------------------------
# Discrete copy number alterations (GISTIC-style -2/-1/0/1/2 calls)
# --------------------------------------------------------------------------


@mcp.tool()
async def get_discrete_copy_number(
    molecular_profile_id: str,
    sample_list_id: str,
    discrete_copy_number_event_type: Literal["HOMDEL", "HETLOSS", "DIPLOID", "GAIN", "AMP", "ALL"] = "ALL",
    projection: Projection = "SUMMARY",
) -> Any:
    """Get discrete copy number alteration calls (e.g. AMP, HOMDEL) for a whole sample list (cohort)
    in a discrete-CNA molecular profile such as 'acc_tcga_gistic'."""
    return await client.get(
        f"/molecular-profiles/{molecular_profile_id}/discrete-copy-number",
        {
            "sampleListId": sample_list_id,
            "discreteCopyNumberEventType": discrete_copy_number_event_type,
            "projection": projection,
        },
    )


@mcp.tool()
async def fetch_discrete_copy_number(
    molecular_profile_id: str,
    sample_ids: list[str] | None = None,
    sample_list_id: str | None = None,
    entrez_gene_ids: list[int] | None = None,
    discrete_copy_number_event_type: Literal["HOMDEL", "HETLOSS", "DIPLOID", "GAIN", "AMP", "ALL"] = "ALL",
    projection: Projection = "SUMMARY",
) -> Any:
    """Fetch discrete copy number alteration calls for specific sample_ids (or a sample_list_id) and,
    optionally, specific entrez_gene_ids."""
    body: dict[str, Any] = {}
    if sample_ids:
        body["sampleIds"] = sample_ids
    if sample_list_id:
        body["sampleListId"] = sample_list_id
    if entrez_gene_ids:
        body["entrezGeneIds"] = entrez_gene_ids
    return await client.post(
        f"/molecular-profiles/{molecular_profile_id}/discrete-copy-number/fetch",
        body,
        {"discreteCopyNumberEventType": discrete_copy_number_event_type, "projection": projection},
    )


# --------------------------------------------------------------------------
# Copy number segments (raw segmented copy-number log2 ratios)
# --------------------------------------------------------------------------


@mcp.tool()
async def get_sample_copy_number_segments(
    study_id: str,
    sample_id: str,
    chromosome: str | None = None,
    page_number: int = 0,
    page_size: int = 500,
) -> Any:
    """Get raw copy-number segments (chromosome, start, end, log2 ratio) for one sample, optionally
    filtered to one chromosome."""
    return await client.get(
        f"/studies/{study_id}/samples/{sample_id}/copy-number-segments",
        {**_paging(page_number, page_size, None, "ASC"), "chromosome": chromosome},
    )


@mcp.tool()
async def fetch_copy_number_segments(
    sample_identifiers: list[SampleIdentifier], chromosome: str | None = None, projection: Projection = "SUMMARY"
) -> Any:
    """Fetch raw copy-number segments for several samples at once (across one or more studies)."""
    body = [s.model_dump() for s in sample_identifiers]
    return await client.post("/copy-number-segments/fetch", body, {"chromosome": chromosome, "projection": projection})


# --------------------------------------------------------------------------
# Generic assay data (e.g. treatment response / other non-gene-centric assays)
# --------------------------------------------------------------------------


@mcp.tool()
async def fetch_generic_assay_data_in_profile(
    molecular_profile_id: str,
    sample_ids: list[str] | None = None,
    sample_list_id: str | None = None,
    generic_assay_stable_ids: list[str] | None = None,
    projection: Projection = "SUMMARY",
) -> Any:
    """Fetch generic assay data (e.g. drug response IC50, other non-gene-centric assay values) within
    one molecular profile, for specific sample_ids (or a sample_list_id) and specific assay IDs."""
    body: dict[str, Any] = {}
    if sample_ids:
        body["sampleIds"] = sample_ids
    if sample_list_id:
        body["sampleListId"] = sample_list_id
    if generic_assay_stable_ids:
        body["genericAssayStableIds"] = generic_assay_stable_ids
    return await client.post(f"/generic_assay_data/{molecular_profile_id}/fetch", body, {"projection": projection})


@mcp.tool()
async def fetch_generic_assay_data_multi_study(
    molecular_profile_ids: list[str] | None = None,
    sample_molecular_identifiers: list[SampleMolecularIdentifier] | None = None,
    generic_assay_stable_ids: list[str] | None = None,
    projection: Projection = "SUMMARY",
) -> Any:
    """Fetch generic assay data across several molecular profiles/studies at once."""
    body: dict[str, Any] = {}
    if molecular_profile_ids:
        body["molecularProfileIds"] = molecular_profile_ids
    if sample_molecular_identifiers:
        body["sampleMolecularIdentifiers"] = [s.model_dump() for s in sample_molecular_identifiers]
    if generic_assay_stable_ids:
        body["genericAssayStableIds"] = generic_assay_stable_ids
    return await client.post("/generic_assay_data/fetch", body, {"projection": projection})


@mcp.tool()
async def fetch_generic_assay_meta(
    molecular_profile_ids: list[str] | None = None,
    generic_assay_stable_ids: list[str] | None = None,
    projection: Projection = "SUMMARY",
) -> Any:
    """Fetch metadata (name, description, unit) for generic assay entities, by molecular_profile_ids
    and/or explicit generic_assay_stable_ids."""
    body: dict[str, Any] = {}
    if molecular_profile_ids:
        body["molecularProfileIds"] = molecular_profile_ids
    if generic_assay_stable_ids:
        body["genericAssayStableIds"] = generic_assay_stable_ids
    return await client.post("/generic_assay_meta/fetch", body, {"projection": projection})


# --------------------------------------------------------------------------
# Treatments
# --------------------------------------------------------------------------


@mcp.tool()
async def fetch_sample_treatments(study_ids: list[str], sample_identifiers: list[SampleIdentifier] | None = None) -> Any:
    """Get sample-level treatment records (e.g. chemotherapy regimens) for a set of studies, optionally
    restricted to specific samples."""
    study_view_filter: dict[str, Any] = {"studyIds": study_ids}
    if sample_identifiers:
        study_view_filter["sampleIdentifiers"] = [s.model_dump() for s in sample_identifiers]
    return await client.post("/treatments/sample", study_view_filter)


@mcp.tool()
async def fetch_patient_treatments(study_ids: list[str], sample_identifiers: list[SampleIdentifier] | None = None) -> Any:
    """Get patient-level treatment records (e.g. chemotherapy regimens) for a set of studies, optionally
    restricted to specific samples (used to select the patients)."""
    study_view_filter: dict[str, Any] = {"studyIds": study_ids}
    if sample_identifiers:
        study_view_filter["sampleIdentifiers"] = [s.model_dump() for s in sample_identifiers]
    return await client.post("/treatments/patient", study_view_filter)


# --------------------------------------------------------------------------
# Escape hatch: raw request for anything not covered above
# --------------------------------------------------------------------------


@mcp.tool()
async def raw_api_request(
    method: Literal["GET", "POST"],
    path: str,
    query_params: dict[str, Any] | None = None,
    json_body: Any = None,
) -> Any:
    """Make a raw request to any cBioPortal REST API endpoint not covered by the other tools
    (see https://www.cbioportal.org/api/swagger-ui/index.html for the full list). `path` is relative
    to the API base, e.g. '/studies/acc_tcga/clinical-attributes'. Use this for advanced use cases such
    as a full StudyViewFilter on /treatments/sample or /treatments/patient."""
    if method == "GET":
        return await client.get(path, query_params)
    return await client.post(path, json_body, query_params)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
