# ClinicalTrials.gov Public Data MCP Server

A read-only [MCP](https://modelcontextprotocol.io/) server for live queries to the public
[ClinicalTrials.gov REST API v2](https://clinicaltrials.gov/data-api/api).

It exposes a focused workflow:

1. `search_recent_open_trials` finds still-open trials for a cancer type that started within
   the last N years (default 2), along with each trial's drugs/interventions and a best-effort
   guess at targeted genes drawn from the trial's own keywords.
2. `get_trial_details` retrieves the full record for one trial by NCT ID.

"Open" means the trial's `overallStatus` is `RECRUITING`, `NOT_YET_RECRUITING`,
`ENROLLING_BY_INVITATION`, or `ACTIVE_NOT_RECRUITING`.

## On the "targeted genes" field

ClinicalTrials.gov has no structured target-gene field. `candidate_target_genes` is a
best-effort heuristic scan of each trial's own submitter-provided keywords for gene-symbol-like
tokens (all-caps, not a known mutation notation like `V600E`, not a common non-gene acronym). It
can both miss real targets (e.g. a keyword written as "Braf" instead of "BRAF", or a hyphenated
symbol like "PD-L1") and include false positives (other all-caps acronyms, drug development
codes, abbreviations like "RH+"). Treat it as a lead worth checking, not ground truth.

The server never alters ClinicalTrials.gov data. It uses `https://clinicaltrials.gov/api/v2` by
default; set `CLINICALTRIALS_API_BASE_URL` to use another compatible endpoint.

## Running

```bash
pip install -r requirements.txt
python server.py
```

For interactive inspection:

```bash
uv run --with "mcp[cli]" --with httpx mcp dev server.py
```

## API sources

- [ClinicalTrials.gov API and API Clients documentation](https://clinicaltrials.gov/data-api/api)
