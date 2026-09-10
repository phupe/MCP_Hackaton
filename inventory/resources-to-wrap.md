# Resources worth wrapping

Databases, tools and model formats used in cancer systems biology that have **no MCP server we
know of**, or only a thin third-party one. This is the shopping list for Day 2.

> **Seed list — organisers to prune.** These are well-known resources in the field, gathered as
> starting points for group brainstorming on Day 1. It is not a vetted set of recommendations,
> and no claim is made here about which ones have an MCP server we have not found.

## How to read this as a project proposal

A good hackathon target has three properties:

1. **A programmatic interface already exists** — a REST API, a Python package, a CLI. If you
   would have to scrape HTML, pick something else for a 1.5-day event.
2. **A question you actually ask** — the tool surface should come from your own work, not from
   the API's endpoint list. A server that mirrors 40 endpoints is worse than one with four tools
   that answer four real questions.
3. **It fits in a demo** — you need to show it working at 17:00 on Friday.

The second point is the one that separates the good Day 2 projects from the tedious ones. An MCP
server is not an API client; it is an opinionated interface designed for a reader who has no
memory and infinite patience.

## The Institut Curie / CoLoMoTo modelling stack

Partly covered already — NeKo, MaBoSS and PhysiCell have servers (see
[`mcp-servers.md`](mcp-servers.md)). The rest of the ecosystem does not.

| Resource | Interface | What a server would add |
| --- | --- | --- |
| [GINsim](https://ginsim.org) | Java, GINML files | logical model editing and attractor analysis |
| [BoolNet](https://cran.r-project.org/package=BoolNet) | R package | Boolean model inference and attractor search |
| [CoLoMoTo notebook](https://colomoto.github.io) | Docker, Python | the whole logical-modelling toolchain in one place |
| [bioLQM](https://colomoto.github.io/biolqm/) | Java/Python | conversion between logical model formats |
| [CellCollective](https://cellcollective.org) | REST | a library of published logical models |
| [PhysiCell Studio](https://github.com/PhysiCell-Tools/PhysiCell-Studio) | Python GUI | agent-based model configuration beyond the existing server |
| [OmniPath / pypath](https://omnipathdb.org) | REST + Python | prior-knowledge networks; NeKo reaches it, nothing exposes it directly |
| [CellNOpt](https://saezlab.github.io/CellNOptR/) | R | fitting logical models to perturbation data |
| [decoupleR](https://saezlab.github.io/decoupleR/) | R + Python | pathway and TF activity inference |
| SBML / SBML-qual | file format | model exchange, validation, round-tripping |

## Cancer genomics and clinical data

| Resource | Interface | Notes |
| --- | --- | --- |
| [cBioPortal](https://www.cbioportal.org) | well-documented REST API | the obvious gap. BioMCP analyses downloaded cBioPortal-style files but is not a live client |
| [COSMIC](https://cancer.sanger.ac.uk/cosmic) | REST, downloads | licence terms need checking before anything is published |
| [DepMap](https://depmap.org) | downloads, API | dependency and CRISPR screens; a natural fit for target prioritisation |
| [GDC / TCGA](https://portal.gdc.cancer.gov) | REST | large, well-specified, genuinely useful |
| [ICGC ARGO](https://www.icgc-argo.org) | REST | international cohorts |
| [OncoKB](https://www.oncokb.org) | REST, token required | reached through BioMCP; licence-gated |
| [CIViC](https://civicdb.org) | REST | clinical interpretation of variants, openly licensed |
| [ClinVar](https://www.ncbi.nlm.nih.gov/clinvar/) | E-utilities | reached through BioMCP |
| [cellxgene / CZ CELLxGENE](https://cellxgene.cziscience.com) | Python, REST | single-cell atlases |

## Pathways, signatures, enrichment

| Resource | Interface | Notes |
| --- | --- | --- |
| [MSigDB / GSEA](https://www.gsea-msigdb.org) | downloads, REST | signature retrieval and enrichment; a strong small project |
| [Reactome](https://reactome.org) | REST | third-party server exists; an official one does not |
| [WikiPathways](https://www.wikipathways.org) | REST | openly licensed pathway content |
| [g:Profiler](https://biit.cs.ut.ee/gprofiler/) | REST | reached through BioMCP |
| [Enrichr](https://maayanlab.cloud/Enrichr/) | REST | simple API, immediate payoff |
| [SIGNOR](https://signor.uniroma2.it) | REST | causal interactions, directly useful for Boolean models |

## Your own institute

The highest-value category, and the one nobody else can build:

- a cohort or registry your group maintains
- pipeline outputs sitting on a shared filesystem or an HPC scratch directory
- an image store, a LIMS, an electronic lab notebook
- the spreadsheet that is, in practice, the lab's database
- a model your group published, so that others can interrogate it conversationally

If you bring one of these to Day 1, you are ahead of everyone starting from a public API. Two
warnings, though. **Patient-adjacent data does not go into a hackathon prototype** — build
against synthetic or already-public data and connect the real source afterwards, under whatever
governance applies to it. And a server that reads a shared filesystem needs its path handling
thought about on day one, not retrofitted.
