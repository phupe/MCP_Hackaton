"""Read-only MCP server for the public ClinicalTrials.gov REST API (v2)."""

from __future__ import annotations

import logging
import os
import re
from datetime import date, timedelta
from typing import Annotated, Any

import httpx
from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field

API_BASE_URL = os.environ.get("CLINICALTRIALS_API_BASE_URL", "https://clinicaltrials.gov/api/v2").rstrip("/")
MAX_RESULTS = 50
DEFAULT_YEARS = 2
MAX_YEARS = 20

# "Open" here means the trial is still enrolling, about to enroll, or ongoing without further
# enrollment - i.e. not yet closed out. See ClinicalTrials.gov's overallStatus enum.
OPEN_STATUSES = ["RECRUITING", "NOT_YET_RECRUITING", "ENROLLING_BY_INVITATION", "ACTIVE_NOT_RECRUITING"]

SEARCH_FIELDS = (
    "NCTId,BriefTitle,OverallStatus,StartDate,Phase,LeadSponsorName,Condition,"
    "InterventionType,InterventionName,Keyword"
)

# Heuristics for pulling candidate target-gene symbols out of a trial's own keywords.
# ClinicalTrials.gov has no structured "target gene" field, so this is best-effort: it can
# both miss real targets (e.g. lowercase "Braf") and produce false positives (other all-caps
# acronyms, drug development codes).
_GENE_TOKEN_RE = re.compile(r"[A-Z][A-Z0-9]{1,9}")
_MUTATION_NOTATION_RE = re.compile(r"^[A-Z]\d+[A-Z]?$")  # e.g. V600E, T790M, L858R
_NON_GENE_TOKENS = {
    "II", "III", "IV", "VI", "VII", "VIII", "IX", "XI", "XII",
    "FDA", "NCT", "USA", "US", "UK", "EU", "MRI", "PET", "ECG", "DNA", "RNA", "PCR",
    "IRB", "QOL", "OS", "PFS", "ORR", "AE", "SAE", "RCT", "ICH", "GCP", "CT", "ID",
}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("clinicaltrials-mcp")

mcp = MCPServer(
    "ClinicalTrials.gov Public Data",
    instructions=(
        "Read-only tools for the public ClinicalTrials.gov REST API v2. Use "
        "search_recent_open_trials with a cancer type to find still-open trials that started "
        "within the last N years (default 2), along with the drugs/interventions they test and "
        "a best-effort guess at targeted genes drawn from each trial's own keywords. Use "
        "get_trial_details for the full text of one trial found that way. "
        "The server queries public ClinicalTrials.gov data live and does not modify it."
    ),
)


async def _request(method: str, path: str, *, params: dict[str, Any] | None = None) -> Any:
    """Call the public API and turn recoverable HTTP failures into ToolErrors."""
    url = f"{API_BASE_URL}{path}"
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
            response = await client.request(method, url, params=params)
    except httpx.TimeoutException as exc:
        raise ToolError("ClinicalTrials.gov did not respond within 30 seconds. Please retry.") from exc
    except httpx.RequestError as exc:
        raise ToolError(f"Could not reach ClinicalTrials.gov at {API_BASE_URL}. Please retry later.") from exc

    if response.status_code == 404:
        raise ToolError("ClinicalTrials.gov did not find that resource. Check the NCT ID and retry.")
    if response.status_code == 429:
        raise ToolError("ClinicalTrials.gov rate-limited this request. Wait briefly, then retry.")
    if response.is_error:
        raise ToolError(
            f"ClinicalTrials.gov returned HTTP {response.status_code}. Check the supplied "
            "parameters and retry."
        )
    try:
        return response.json()
    except ValueError as exc:
        raise ToolError("ClinicalTrials.gov returned an unexpected non-JSON response. Please retry.") from exc


def _extract_candidate_genes(keywords: list[str]) -> list[str]:
    """Best-effort scan of a trial's own keywords for gene-symbol-like tokens."""
    candidates: list[str] = []
    seen: set[str] = set()
    for keyword in keywords:
        for raw_token in re.findall(r"[A-Za-z0-9-]+", keyword):
            token = raw_token.strip("-")
            if not token or token != token.upper():
                continue  # only consider tokens the submitter already wrote in caps
            if token in _NON_GENE_TOKENS or _MUTATION_NOTATION_RE.match(token):
                continue
            if sum(character.isdigit() for character in token) >= 4:
                continue  # likely a compound/drug development code, not a gene symbol
            if not _GENE_TOKEN_RE.fullmatch(token) or token in seen:
                continue
            seen.add(token)
            candidates.append(token)
    return candidates


class Intervention(BaseModel):
    intervention_type: str
    name: str


class ClinicalTrial(BaseModel):
    nct_id: str
    brief_title: str
    overall_status: str
    start_date: str | None = None
    phases: list[str] = Field(default_factory=list)
    lead_sponsor: str | None = None
    conditions: list[str] = Field(default_factory=list)
    interventions: list[Intervention] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    candidate_target_genes: list[str] = Field(default_factory=list)


def _trial(raw: dict[str, Any]) -> ClinicalTrial:
    protocol = raw["protocolSection"]
    identification = protocol.get("identificationModule", {})
    status = protocol.get("statusModule", {})
    conditions_module = protocol.get("conditionsModule", {})
    design = protocol.get("designModule", {})
    sponsor = protocol.get("sponsorCollaboratorsModule", {}).get("leadSponsor", {})
    interventions = protocol.get("armsInterventionsModule", {}).get("interventions", [])
    keywords = conditions_module.get("keywords", [])
    return ClinicalTrial(
        nct_id=identification["nctId"],
        brief_title=identification.get("briefTitle", ""),
        overall_status=status.get("overallStatus", "UNKNOWN"),
        start_date=status.get("startDateStruct", {}).get("date"),
        phases=design.get("phases", []),
        lead_sponsor=sponsor.get("name"),
        conditions=conditions_module.get("conditions", []),
        interventions=[
            Intervention(intervention_type=item.get("type", "UNKNOWN"), name=item["name"])
            for item in interventions
        ],
        keywords=keywords,
        candidate_target_genes=_extract_candidate_genes(keywords),
    )


class OpenTrialSearch(BaseModel):
    cancer_type: str
    years: int
    since_date: str
    open_statuses: list[str]
    total_matching: int
    trials: list[ClinicalTrial]


@mcp.tool(annotations=ToolAnnotations(read_only_hint=True, open_world_hint=True))
async def search_recent_open_trials(
    cancer_type: Annotated[
        str, Field(min_length=1, description="Cancer type or condition, e.g. 'melanoma' or 'non-small cell lung cancer'.")
    ],
    years: Annotated[
        int, Field(ge=1, le=MAX_YEARS, description="How many years back a trial may have started to be included.")
    ] = DEFAULT_YEARS,
    max_results: Annotated[
        int, Field(ge=1, le=MAX_RESULTS, description="Maximum number of trials to return, most recently started first.")
    ] = 10,
) -> OpenTrialSearch:
    """Find still-open trials for a cancer type that started within the last N years.

    Returns each trial's drugs/interventions and a best-effort guess at targeted genes drawn
    from the trial's own keywords (ClinicalTrials.gov has no structured target-gene field, so
    this can miss real targets or include false positives - treat it as a lead, not ground truth).
    "Open" means RECRUITING, NOT_YET_RECRUITING, ENROLLING_BY_INVITATION, or
    ACTIVE_NOT_RECRUITING. Results are sorted by start date, most recent first.
    """
    today = date.today()
    since_date = today - timedelta(days=round(365.25 * years))

    data = await _request(
        "GET",
        "/studies",
        params={
            "query.cond": cancer_type,
            "query.term": f"AREA[StartDate]RANGE[{since_date.isoformat()},{today.isoformat()}]",
            "filter.overallStatus": ",".join(OPEN_STATUSES),
            "fields": SEARCH_FIELDS,
            "sort": "StartDate:desc",
            "pageSize": max_results,
            "countTotal": "true",
        },
    )
    return OpenTrialSearch(
        cancer_type=cancer_type,
        years=years,
        since_date=since_date.isoformat(),
        open_statuses=OPEN_STATUSES,
        total_matching=data.get("totalCount", len(data.get("studies", []))),
        trials=[_trial(item) for item in data.get("studies", [])],
    )


@mcp.tool(annotations=ToolAnnotations(read_only_hint=True, open_world_hint=True))
async def get_trial_details(
    nct_id: Annotated[str, Field(min_length=1, description="NCT ID from search_recent_open_trials, e.g. 'NCT01234567'.")]
) -> ClinicalTrial:
    """Get the full record for one trial by its NCT ID."""
    data = await _request("GET", f"/studies/{nct_id}", params={"fields": SEARCH_FIELDS})
    return _trial(data)


if __name__ == "__main__":
    mcp.run()
