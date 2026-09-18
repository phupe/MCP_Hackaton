"""Read-only MCP server for finding TCGA projects through the NCI GDC API."""

from __future__ import annotations

import os
import json
from typing import Annotated, Any

import httpx
from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field

API_BASE_URL = os.environ.get("TCGA_API_BASE_URL", "https://api.gdc.cancer.gov").rstrip("/")
MAX_RESULTS = 50
READ_ONLY = ToolAnnotations(read_only_hint=True, open_world_hint=True)


class Study(BaseModel):
    study_id: str
    name: str
    description: str | None = None
    cancer_type_id: str | None = None
    sample_count: int | None = None
    reference_genome: str | None = None


class StudySearchResult(BaseModel):
    query: str
    query_type: str
    studies: list[Study]


mcp = MCPServer(
    "TCGA GDC Study Search",
    instructions=(
        "Read-only tools for finding TCGA projects in the public NCI Genomic Data Commons API. "
        "Use search_studies_by_gene for a gene symbol such as TP53 and "
        "search_studies_by_disease for a disease or cancer type such as breast cancer. "
        "Gene searches use GDC somatic mutation records and return the TCGA projects containing "
        "matching mutations; disease searches query GDC project metadata."
    ),
)


async def _request(
    method: str, path: str, *, params: dict[str, Any] | None = None
) -> Any:
    """Call GDC and expose actionable failures to the MCP client."""
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
            response = await client.request(method, f"{API_BASE_URL}{path}", params=params)
    except httpx.TimeoutException as exc:
        raise ToolError("The GDC API did not respond within 30 seconds. Please retry.") from exc
    except httpx.RequestError as exc:
        raise ToolError(f"Could not reach the GDC API at {API_BASE_URL}.") from exc

    if response.status_code == 429:
        raise ToolError("The GDC API rate-limited this request. Wait briefly, then retry.")
    if response.status_code == 404:
        raise ToolError("The GDC API did not find the requested resource.")
    if response.is_error:
        raise ToolError(f"The GDC API returned HTTP {response.status_code}.")
    try:
        return response.json()
    except ValueError as exc:
        raise ToolError("The GDC API returned an unexpected non-JSON response.") from exc


def _study_from_api(study: dict[str, Any]) -> Study:
    return Study(
        study_id=str(study.get("project_id", "")),
        name=str(study.get("name") or study.get("project_id", "")),
        description=study.get("disease_type"),
        cancer_type_id=study.get("primary_site"),
        sample_count=study.get("cases.0"),
        reference_genome=None,
    )


def _tcga_filter(*conditions: dict[str, Any]) -> str:
    return json.dumps(
        {
            "op": "and",
            "content": [
                {"op": "=", "content": {"field": "program.name", "value": "TCGA"}},
                *conditions,
            ],
        }
    )


async def _get_projects(filters: str) -> list[dict[str, Any]]:
    data = await _request(
        "GET",
        "/projects",
        params={
            "filters": filters,
            "size": MAX_RESULTS,
            "format": "JSON",
        },
    )
    return data.get("data", {}).get("hits", [])


async def _search_by_disease(query: str) -> StudySearchResult:
    cleaned_query = query.strip()
    hits = await _get_projects(
        _tcga_filter(
            {
                "op": "or",
                "content": [
                    {"op": "contains", "content": {"field": "disease_type", "value": cleaned_query}},
                    {"op": "contains", "content": {"field": "primary_site", "value": cleaned_query}},
                ],
            }
        )
    )
    return StudySearchResult(
        query=cleaned_query, query_type="disease", studies=[_study_from_api(item) for item in hits]
    )


async def _search_by_gene(query: str) -> StudySearchResult:
    cleaned_query = query.strip()
    data = await _request(
        "GET",
        "/ssm",
        params={
            "filters": json.dumps(
                {
                    "op": "=",
                    "content": {"field": "consequence.transcript.gene.symbol", "value": cleaned_query},
                }
            ),
            "fields": "cases.project.project_id",
            "size": MAX_RESULTS,
            "format": "JSON",
        },
    )
    project_ids = sorted(
        {
            project_id
            for hit in data.get("data", {}).get("hits", [])
            for case in hit.get("cases", [])
            for project in case.get("project", [])
            if (project_id := project.get("project_id", "")).startswith("TCGA-")
        }
    )
    if not project_ids:
        return StudySearchResult(query=cleaned_query, query_type="gene", studies=[])
    hits = await _get_projects(
        _tcga_filter({"op": "in", "content": {"field": "project_id", "value": project_ids}})
    )
    return StudySearchResult(
        query=cleaned_query, query_type="gene", studies=[_study_from_api(item) for item in hits]
    )


@mcp.tool(annotations=READ_ONLY)
async def search_studies_by_gene(
    gene_symbol: Annotated[
        str, Field(min_length=1, description="HGNC gene symbol, for example TP53 or BRCA1.")
    ],
) -> StudySearchResult:
    """Find TCGA projects containing GDC somatic mutations in a gene."""
    return await _search_by_gene(gene_symbol)


@mcp.tool(annotations=READ_ONLY)
async def search_studies_by_disease(
    disease: Annotated[
        str, Field(min_length=1, description="Disease or cancer type, for example breast cancer.")
    ],
) -> StudySearchResult:
    """Find TCGA projects whose GDC metadata matches a disease or primary site."""
    return await _search_by_disease(disease)


if __name__ == "__main__":
    mcp.run()
