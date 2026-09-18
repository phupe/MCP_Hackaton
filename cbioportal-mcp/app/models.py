"""Protocol-visible response models for cBioPortal MCP tools."""

from typing import Any

from pydantic import BaseModel, Field


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


class Sample(BaseModel):
    sample_id: str
    patient_id: str
    sample_type: str | None = None


class SampleListPage(BaseModel):
    study_id: str
    page_number: int
    page_size: int
    samples: list[Sample]


class Gene(BaseModel):
    entrez_gene_id: int
    hugo_gene_symbol: str
    gene_type: str | None = None


class GeneLookup(BaseModel):
    requested_symbols: list[str]
    genes: list[Gene]


class MutationQueryResult(BaseModel):
    molecular_profile_id: str
    sample_ids: list[str]
    entrez_gene_ids: list[int]
    mutations: list[dict[str, Any]]


class StudyAlterationResult(BaseModel):
    study: Study
    molecular_profile_id: str | None = None
    sample_list_id: str | None = None
    genes: list[Gene]
    mutations: list[dict[str, Any]]


class PatientMutation(BaseModel):
    patient_id: str
    sample_ids: list[str]
    mutations: list[dict[str, Any]]
    clinical_data: dict[str, Any] = Field(default_factory=dict)


class PatientMutationCohort(BaseModel):
    study_id: str
    molecular_profile_id: str
    sample_list_id: str
    gene: Gene
    protein_change: str
    patients: list[PatientMutation]
