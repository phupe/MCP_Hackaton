"""Small request-body building blocks shared by several cBioPortal POST endpoints.

These mirror the OpenAPI `definitions` used across the `/…/fetch` endpoints
(see https://www.cbioportal.org/api/v2/api-docs) so tool parameters get a
clear, self-describing JSON schema instead of an opaque free-form dict.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class SampleIdentifier(BaseModel):
    studyId: str = Field(description="Study ID, e.g. 'acc_tcga'")
    sampleId: str = Field(description="Sample ID, e.g. 'TCGA-OR-A5J2-01'")


class PatientIdentifier(BaseModel):
    studyId: str = Field(description="Study ID, e.g. 'acc_tcga'")
    patientId: str = Field(description="Patient ID, e.g. 'TCGA-OR-A5J2'")


class ClinicalDataIdentifier(BaseModel):
    studyId: str = Field(description="Study ID, e.g. 'acc_tcga'")
    entityId: str = Field(description="Sample ID or Patient ID, depending on clinicalDataType")


class SampleMolecularIdentifier(BaseModel):
    molecularProfileId: str = Field(description="Molecular Profile ID, e.g. 'acc_tcga_mutations'")
    sampleId: str = Field(description="Sample ID, e.g. 'TCGA-OR-A5J2-01'")
