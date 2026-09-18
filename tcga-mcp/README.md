# TCGA Study Search MCP Server

This read-only MCP server finds TCGA projects through the public NCI Genomic Data Commons (GDC) API.
It provides:

- `search_studies_by_gene` for symbols such as `TP53` or `BRCA1`
- `search_studies_by_disease` for terms such as `breast cancer` or `glioblastoma`

Disease searches query GDC project metadata. Gene searches query GDC somatic mutation
records and then resolve the matching TCGA project metadata. It does not modify data.

## Run

```bash
pip install -r requirements.txt
python server.py
```

Set `TCGA_API_BASE_URL` to use another compatible GDC deployment.
