"""Read-only MCP server for the public cBioPortal REST API."""

from __future__ import annotations

import logging
import os
from typing import Annotated, Any
from urllib.parse import quote

import httpx
from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field

API_BASE_URL = os.environ.get("CBIOPORTAL_API_BASE_URL", "https://www.cbioportal.org/api").rstrip("/")
MAX_PAGE_SIZE = 100
MAX_MUTATION_SAMPLES = 100
MAX_MUTATION_GENES = 100

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("cbioportal-mcp")

mcp = MCPServer(
    "cBioPortal Public Data",
    instructions=(
        "Read-only tools for the public cBioPortal REST API. First use list_studies to find "
        "a study, then get_study_data_catalog to select a molecular profile and sample list. "
        "Use lookup_genes to turn Hugo gene symbols into Entrez IDs before fetch_mutations. "
        "The server queries public cBioPortal data live and does not modify portal data."
    ),
)


async def _request(
    method: str, path: str, *, params: dict[str, Any] | None = None, json: Any = None
) -> Any:
    """Call the public API and turn recoverable HTTP failures into ToolErrors."""
    url = f"{API_BASE_URL}{path}"
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
            response = await client.request(method, url, params=params, json=json)
    except httpx.TimeoutException as exc:
        raise ToolError("cBioPortal did not respond within 30 seconds. Please retry.") from exc
    except httpx.RequestError as exc:
        raise ToolError(f"Could not reach cBioPortal at {API_BASE_URL}. Please retry later.") from exc

    if response.status_code == 404:
        raise ToolError(
            "cBioPortal did not find that resource. Check the study, profile, sample, or gene "
            "identifier and discover valid IDs with the list tools."
        )
    if response.status_code == 401 or response.status_code == 403:
        raise ToolError(
            "This cBioPortal resource is not public. Choose a public study or configure an "
            "authorized API endpoint with CBIOPORTAL_API_BASE_URL."
        )
    if response.status_code == 429:
        raise ToolError("cBioPortal rate-limited this request. Wait briefly, then retry.")
    if response.is_error:
        raise ToolError(
            f"cBioPortal returned HTTP {response.status_code}. Check the supplied identifiers "
            "and retry."
        )
    try:
        return response.json()
    except ValueError as exc:
        raise ToolError("cBioPortal returned an unexpected non-JSON response. Please retry.") from exc


class Study(BaseModel):
    study_id: str
    name: str
    description: str | None = None
    cancer_type_id: str | None = None
    sample_count: int | None = None
    reference_genome: str | None = None


class StudyList(BaseModel):
    page_number: int
    page_size: int
    studies: list[Study]


def _study(raw: dict[str, Any]) -> Study:
    return Study(
        study_id=raw["studyId"],
        name=raw.get("name", raw["studyId"]),
        description=raw.get("description"),
        cancer_type_id=raw.get("cancerTypeId"),
        sample_count=raw.get("allSampleCount"),
        reference_genome=raw.get("referenceGenome"),
    )


@mcp.tool(annotations=ToolAnnotations(read_only_hint=True, open_world_hint=True))
async def list_studies(
    page_number: Annotated[int, Field(ge=0, description="Zero-based page number.")] = 0,
    page_size: Annotated[
        int, Field(ge=1, le=MAX_PAGE_SIZE, description="Number of public studies to return.")
    ] = 25,
) -> StudyList:
    """List public cBioPortal studies to identify a study ID for downstream queries."""
    data = await _request(
        "GET",
        "/studies",
        params={
            "pageNumber": page_number,
            "pageSize": page_size,
            "projection": "SUMMARY",
            "sortBy": "name",
            "direction": "ASC",
        },
    )
    return StudyList(page_number=page_number, page_size=page_size, studies=[_study(item) for item in data])


class MolecularProfile(BaseModel):
    molecular_profile_id: str
    name: str
    molecular_alteration_type: str
    datatype: str
    description: str | None = None


class SampleList(BaseModel):
    sample_list_id: str
    name: str
    description: str | None = None
    sample_count: int | None = None


class StudyDataCatalog(BaseModel):
    study: Study
    molecular_profiles: list[MolecularProfile]
    sample_lists: list[SampleList]


@mcp.tool(annotations=ToolAnnotations(read_only_hint=True, open_world_hint=True))
async def get_study_data_catalog(
    study_id: Annotated[str, Field(min_length=1, description="cBioPortal study ID from list_studies.")]
) -> StudyDataCatalog:
    """Get a study plus its molecular profiles and sample lists for choosing data to query."""
    encoded_study_id = quote(study_id, safe="")
    study_data, profiles, sample_lists = await _request(
        "GET", f"/studies/{encoded_study_id}", params={"projection": "SUMMARY"}
    ), await _request(
        "GET", f"/studies/{encoded_study_id}/molecular-profiles", params={"projection": "SUMMARY"}
    ), await _request(
        "GET", f"/studies/{encoded_study_id}/sample-lists", params={"projection": "SUMMARY"}
    )
    return StudyDataCatalog(
        study=_study(study_data),
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


class Sample(BaseModel):
    sample_id: str
    patient_id: str
    sample_type: str | None = None


class SampleListPage(BaseModel):
    study_id: str
    page_number: int
    page_size: int
    samples: list[Sample]


@mcp.tool(annotations=ToolAnnotations(read_only_hint=True, open_world_hint=True))
async def list_study_samples(
    study_id: Annotated[
        str, Field(min_length=1, description="cBioPortal study ID from list_studies.")
    ],
    page_number: Annotated[int, Field(ge=0, description="Zero-based page number.")] = 0,
    page_size: Annotated[
        int, Field(ge=1, le=MAX_PAGE_SIZE, description="Number of samples to return.")
    ] = 25,
) -> SampleListPage:
    """List a bounded page of samples in a study for use with fetch_mutations."""
    data = await _request(
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


class Gene(BaseModel):
    entrez_gene_id: int
    hugo_gene_symbol: str
    gene_type: str | None = None


class GeneLookup(BaseModel):
    requested_symbols: list[str]
    genes: list[Gene]


@mcp.tool(annotations=ToolAnnotations(read_only_hint=True, open_world_hint=True))
async def lookup_genes(
    symbols: Annotated[
        list[Annotated[str, Field(min_length=1)]],
        Field(min_length=1, max_length=MAX_MUTATION_GENES, description="Hugo gene symbols, e.g. ['TP53', 'BRCA1']."),
    ]
) -> GeneLookup:
    """Look up Hugo gene symbols and return the Entrez IDs needed for molecular-data queries."""
    normalized_symbols = [symbol.strip().upper() for symbol in symbols]
    data: list[dict[str, Any]] = []
    for symbol in normalized_symbols:
        matches = await _request(
            "GET",
            "/genes",
            params={"keyword": symbol, "pageNumber": 0, "pageSize": 100, "projection": "SUMMARY"},
        )
        data.extend(item for item in matches if item.get("hugoGeneSymbol", "").upper() == symbol)
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


class MutationQueryResult(BaseModel):
    molecular_profile_id: str
    sample_ids: list[str]
    entrez_gene_ids: list[int]
    mutations: list[dict[str, Any]]


@mcp.tool(annotations=ToolAnnotations(read_only_hint=True, open_world_hint=True))
async def fetch_mutations(
    molecular_profile_id: Annotated[
        str, Field(min_length=1, description="Mutation molecular profile ID from get_study_data_catalog.")
    ],
    sample_ids: Annotated[
        list[Annotated[str, Field(min_length=1)]],
        Field(min_length=1, max_length=MAX_MUTATION_SAMPLES, description="Explicit sample IDs (maximum 100)."),
    ],
    entrez_gene_ids: Annotated[
        list[Annotated[int, Field(gt=0)]],
        Field(min_length=1, max_length=MAX_MUTATION_GENES, description="Entrez gene IDs from lookup_genes (maximum 100)."),
    ],
) -> MutationQueryResult:
    """Fetch mutations for explicit samples and genes from a mutation molecular profile.

    Use get_study_data_catalog to find the profile and lookup_genes for Entrez IDs. This tool
    deliberately requires bounded explicit sample and gene sets to avoid accidental cohort-wide
    downloads.
    """
    data = await _request(
        "POST",
        f"/molecular-profiles/{quote(molecular_profile_id, safe='')}/mutations/fetch",
        params={"projection": "SUMMARY"},
        json={"sampleIds": sample_ids, "entrezGeneIds": entrez_gene_ids},
    )
    return MutationQueryResult(
        molecular_profile_id=molecular_profile_id,
        sample_ids=sample_ids,
        entrez_gene_ids=entrez_gene_ids,
        mutations=data,
    )


if __name__ == "__main__":
    mcp.run()
