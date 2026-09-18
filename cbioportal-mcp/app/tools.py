"""MCP tool definitions for cBioPortal queries."""

import asyncio
from typing import Annotated, Any
from urllib.parse import quote

from mcp.server import MCPServer
from mcp.types import ToolAnnotations
from pydantic import Field

from . import api, services
from .models import (
    GeneLookup,
    MutationQueryResult,
    PatientMutationCohort,
    SampleListPage,
    StudyAlterationResult,
    StudyDataCatalog,
    StudyList,
)

MAX_PAGE_SIZE = 100
MAX_MUTATION_SAMPLES = 100
MAX_MUTATION_GENES = 100
READ_ONLY = ToolAnnotations(read_only_hint=True, open_world_hint=True)


def register_tools(mcp: MCPServer) -> None:
    """Register the complete stable cBioPortal MCP tool surface."""

    @mcp.tool(annotations=READ_ONLY)
    async def list_studies(
        page_number: Annotated[int, Field(ge=0, description="Zero-based page number.")] = 0,
        page_size: Annotated[
            int, Field(ge=1, le=MAX_PAGE_SIZE, description="Number of public studies to return.")
        ] = 25,
    ) -> StudyList:
        """List public cBioPortal studies to identify a study ID for downstream queries."""
        data = await api.request(
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
        return StudyList(
            page_number=page_number,
            page_size=page_size,
            studies=[services.study_from_api(item) for item in data],
        )

    @mcp.tool(annotations=READ_ONLY)
    async def search_studies(
        keyword: Annotated[str | None, Field(description="Optional text passed to cBioPortal's study search.")] = None,
        cancer_type_id: Annotated[
            str | None,
            Field(description="Optional cBioPortal cancer type ID, for example nbl or aml."),
        ] = None,
        filter_text: Annotated[
            str | None,
            Field(
                description=(
                    "Optional case-insensitive text filter applied locally to study ID, name, "
                    "description, and cancer type ID."
                )
            ),
        ] = None,
        page_number: Annotated[int, Field(ge=0, description="Zero-based page number.")] = 0,
        page_size: Annotated[
            int, Field(ge=1, le=MAX_PAGE_SIZE, description="Number of public studies to return.")
        ] = 25,
    ) -> StudyList:
        """Search public studies by keyword, cancer type, or pediatric focus."""
        params: dict[str, Any] = {
            "pageNumber": page_number,
            "pageSize": page_size,
            "projection": "SUMMARY",
            "sortBy": "name",
            "direction": "ASC",
        }
        if keyword and keyword.strip():
            params["keyword"] = keyword.strip()
        if cancer_type_id and cancer_type_id.strip():
            params["cancerTypeId"] = cancer_type_id.strip()
        data = await api.request("GET", "/studies", params=params)
        if filter_text and filter_text.strip():
            normalized_filter = filter_text.strip().casefold()
            data = [
                item
                for item in data
                if normalized_filter
                in " ".join(
                    str(item.get(field, "")).casefold()
                    for field in ("studyId", "name", "description", "cancerTypeId")
                )
            ]
        return StudyList(
            page_number=page_number,
            page_size=page_size,
            studies=[services.study_from_api(item) for item in data],
        )

    @mcp.tool(annotations=READ_ONLY)
    async def get_study_data_catalog(
        study_id: Annotated[str, Field(min_length=1, description="cBioPortal study ID from list_studies.")]
    ) -> StudyDataCatalog:
        """Get a study plus its molecular profiles and sample lists for choosing data to query."""
        return await services.get_study_data_catalog(study_id)

    @mcp.tool(annotations=READ_ONLY)
    async def list_study_samples(
        study_id: Annotated[str, Field(min_length=1, description="cBioPortal study ID from list_studies.")],
        page_number: Annotated[int, Field(ge=0, description="Zero-based page number.")] = 0,
        page_size: Annotated[
            int, Field(ge=1, le=MAX_PAGE_SIZE, description="Number of samples to return.")
        ] = 25,
    ) -> SampleListPage:
        """List a bounded page of samples in a study for use with fetch_mutations."""
        return await services.list_study_samples(study_id, page_number, page_size)

    @mcp.tool(annotations=READ_ONLY)
    async def lookup_genes(
        symbols: Annotated[
            list[Annotated[str, Field(min_length=1)]],
            Field(
                min_length=1,
                max_length=MAX_MUTATION_GENES,
                description="Hugo gene symbols, e.g. ['TP53', 'BRCA1'].",
            ),
        ]
    ) -> GeneLookup:
        """Look up Hugo gene symbols and return the Entrez IDs needed for molecular-data queries."""
        return await services.lookup_genes(symbols)

    @mcp.tool(annotations=READ_ONLY)
    async def find_patients_with_mutation(
        study_id: Annotated[str, Field(min_length=1, description="cBioPortal study ID.")],
        gene_symbol: Annotated[
            str, Field(min_length=1, description="Hugo gene symbol, for example BRAF.")
        ],
        protein_change: Annotated[
            str,
            Field(
                min_length=1,
                description=(
                    "Exact protein change, for example V600E or p.V600E. The p. prefix and case "
                    "are normalized before matching."
                ),
            ),
        ],
        clinical_attribute_ids: Annotated[
            list[Annotated[str, Field(min_length=1)]] | None,
            Field(
                max_length=100,
                description=(
                    "Optional patient-level clinical attribute IDs to include. Supplying these adds "
                    "one API request. Obtain valid IDs from the study's clinical-attributes endpoint."
                ),
            ),
        ] = None,
    ) -> PatientMutationCohort:
        """Return patients in one study carrying an exact protein mutation in four API requests."""
        return await services.find_patients_with_mutation(
            study_id, gene_symbol, protein_change, clinical_attribute_ids
        )

    @mcp.tool(annotations=READ_ONLY)
    async def fetch_mutations_by_study(
        study_id: Annotated[str, Field(min_length=1, description="cBioPortal study ID.")],
        gene_symbols: Annotated[
            list[Annotated[str, Field(min_length=1)]],
            Field(
                min_length=1,
                max_length=MAX_MUTATION_GENES,
                description="Hugo gene symbols, e.g. ['BRCA1'].",
            ),
        ],
        max_samples: Annotated[
            int, Field(ge=1, le=MAX_MUTATION_SAMPLES, description="Maximum samples queried from the study.")
        ] = MAX_MUTATION_SAMPLES,
    ) -> StudyAlterationResult:
        """Find mutations for gene symbols in one study without manually discovering profile or sample IDs."""
        study, profile_id, sample_list_id = await services.mutation_profile_and_samples(study_id)
        genes = await services.lookup_genes(gene_symbols)
        if profile_id is None or sample_list_id is None or not genes.genes:
            return StudyAlterationResult(
                study=study,
                molecular_profile_id=profile_id,
                sample_list_id=sample_list_id,
                genes=genes.genes,
                mutations=[],
            )
        samples = await services.list_study_samples(study_id, 0, max_samples)
        mutations = await fetch_mutations(
            profile_id,
            [sample.sample_id for sample in samples.samples],
            [gene.entrez_gene_id for gene in genes.genes],
        )
        return StudyAlterationResult(
            study=study,
            molecular_profile_id=profile_id,
            sample_list_id=sample_list_id,
            genes=genes.genes,
            mutations=mutations.mutations,
        )

    @mcp.tool(annotations=READ_ONLY)
    async def find_gene_alterations(
        study_ids: Annotated[
            list[Annotated[str, Field(min_length=1)]],
            Field(min_length=1, max_length=25, description="cBioPortal study IDs to scan."),
        ],
        gene_symbols: Annotated[
            list[Annotated[str, Field(min_length=1)]],
            Field(min_length=1, max_length=MAX_MUTATION_GENES, description="Hugo gene symbols."),
        ],
        max_samples_per_study: Annotated[
            int,
            Field(ge=1, le=MAX_MUTATION_SAMPLES, description="Maximum samples queried per study."),
        ] = MAX_MUTATION_SAMPLES,
    ) -> list[StudyAlterationResult]:
        """Scan bounded pediatric or cancer studies for gene mutations, grouped by study."""
        return list(
            await asyncio.gather(
                *(
                    fetch_mutations_by_study(study_id, gene_symbols, max_samples_per_study)
                    for study_id in dict.fromkeys(study_ids)
                )
            )
        )

    @mcp.tool(annotations=READ_ONLY)
    async def fetch_mutations(
        molecular_profile_id: Annotated[
            str, Field(min_length=1, description="Mutation molecular profile ID from get_study_data_catalog.")
        ],
        sample_ids: Annotated[
            list[Annotated[str, Field(min_length=1)]],
            Field(
                min_length=1,
                max_length=MAX_MUTATION_SAMPLES,
                description="Explicit sample IDs (maximum 100).",
            ),
        ],
        entrez_gene_ids: Annotated[
            list[Annotated[int, Field(gt=0)]],
            Field(
                min_length=1,
                max_length=MAX_MUTATION_GENES,
                description="Entrez gene IDs from lookup_genes (maximum 100).",
            ),
        ],
    ) -> MutationQueryResult:
        """Fetch mutations for explicit samples and genes from a mutation molecular profile."""
        data = await api.request(
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
