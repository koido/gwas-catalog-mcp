# GWAS Catalog MCP Server

## Overview

This MCP server provides a programmatic interface to the [GWAS Catalog REST API](https://www.ebi.ac.uk/gwas/rest/docs/api), enabling access to GWAS study, variant, trait, and association data. The server handles large result sets automatically by providing both in-memory results and file-based storage options. 

## Status

🚧 **Under Active Development** 🚧

This project is currently under active development. Features and APIs may change without notice.

## Dependencies

- `uv`
- `mcp[cli]`
- `fastmcp`
- `requests`

## Directory Structure

```
.
├── server.py             # Main FastMCP server entrypoint
├── utils.py              # Utility functions
├── run_tests.py          # Test runner
├── pyproject.toml        # Project metadata and dependencies
├── README.md             # Usage and documentation
├── tests/                # Test suite and test data
│   ├── run_tests.py
│   ├── input/
│   └── output/
│       ├── success/
│       └── error/
└── ...
```

## Setup and Running

### Install dependencies

```bash
uv sync
```

### Activate the virtual environment

```bash
. .venv/bin/activate
```

### Run the MCP server

```bash
uv run server.py
```

### Run tests

```bash
python tests/run_tests.py
```

## MCP Tool Specification

### Tool name

- GWAS_catalog

### Common Parameters

Most tools support the following common parameters:

| Parameter           | Type    | Default | Description                                           |
|--------------------|---------|---------|-------------------------------------------------------|
| max_items_in_memory| int     | 5000    | Maximum number of items to return in memory           |
| force_to_file      | bool    | False   | Force writing results to file regardless of size      |
| output_dir         | str     | "/tmp"  | Directory for file output when results exceed limit   |
| force_no_file      | bool    | False   | Never write results to file                          |
| remove_links       | bool    | True    | Remove '_links' fields from API responses             |

### Tool Endpoints and Parameters

#### Get study

| Parameter   | Type   | Required | Description                                 | Example        |
|-------------|--------|----------|---------------------------------------------|----------------|
| studyId     | str    | Yes      | GWAS Catalog study identifier               | "GCST000001"   |
| remove_links| bool   | No       | Remove '_links' fields (default: True)      |                |

#### Get association

| Parameter      | Type   | Required | Description                                 | Example        |
|----------------|--------|----------|---------------------------------------------|----------------|
| associationId  | str    | Yes      | GWAS Catalog association identifier         | "123456"       |
| remove_links   | bool   | No       | Remove '_links' fields (default: True)      |                |

#### Get variant

| Parameter   | Type   | Required | Description                                 | Example        |
|-------------|--------|----------|---------------------------------------------|----------------|
| variantId   | str    | Yes      | Variant identifier (e.g., rsID)             | "rs123"        |
| remove_links| bool   | No       | Remove '_links' fields (default: True)      |                |

#### Get trait

| Parameter   | Type   | Required | Description                                 | Example        |
|-------------|--------|----------|---------------------------------------------|----------------|
| efoId       | str    | Yes      | EFO trait identifier                        | "EFO_0000305"  |
| remove_links| bool   | No       | Remove '_links' fields (default: True)      |                |

#### Search variants in region

| Parameter   | Type   | Required | Description                                 | Example        |
|-------------|--------|----------|---------------------------------------------|----------------|
| chromosome  | str    | Yes      | Chromosome (e.g., "1")                      | "1"            |
| start       | int    | Yes      | Start position (GRCh38/hg38)                | 1000000        |
| end         | int    | Yes      | End position (GRCh38/hg38)                  | 2000000        |
| efo_id      | str    | No       | EFO trait identifier                        | "EFO_0008531"  |
| ...common   |        |          | See common parameters above                 |                |

#### Get variants from EFO IDs

| Parameter   | Type   | Required | Description                                 | Example        |
|-------------|--------|----------|---------------------------------------------|----------------|
| efo_ids     | list   | Yes      | List of EFO trait identifiers               | ["EFO_0000305", "EFO_0000310"] |
| ...common   |        |          | See common parameters above                 |                |

#### Trait variant ranking

| Parameter   | Type   | Required | Description                                 | Example        |
|-------------|--------|----------|---------------------------------------------|----------------|
| efo_id      | str    | Yes      | EFO trait identifier                        | "EFO_0008531"  |
| top_n       | int    | No       | Number of top records to return (default: 10)| 10            |
| ...common   |        |          | See common parameters above                 |                |

#### Get study associations

| Parameter   | Type   | Required | Description                                 | Example        |
|-------------|--------|----------|---------------------------------------------|----------------|
| studyId     | str    | Yes      | GWAS Catalog study identifier               | "GCST000001"   |
| ...common   |        |          | See common parameters above                 |                |

#### Get trait studies

| Parameter   | Type   | Required | Description                                 | Example        |
|-------------|--------|----------|---------------------------------------------|----------------|
| efoId       | str    | Yes      | EFO trait identifier                        | "EFO_0000305"  |
| ...common   |        |          | See common parameters above                 |                |

#### Get trait associations

| Parameter   | Type   | Required | Description                                 | Example        |
|-------------|--------|----------|---------------------------------------------|----------------|
| efoId       | str    | Yes      | EFO trait identifier                        | "EFO_0000305"  |
| ...common   |        |          | See common parameters above                 |                |

#### Get associations from variant *(uses GWAS Catalog REST API)*

| Parameter   | Type   | Required | Description                                 | Example        |
|-------------|--------|----------|---------------------------------------------|----------------|
| variantId   | str    | Yes      | Variant identifier                          | "rs112735431"  |
| ...common   |        |          | See common parameters above                 |                |

> **Note:** This method returns all associations for a variant, including an `is_gwas_significant` flag indicating if the p-value meets the genome-wide significance threshold (p ≤ 5e-8). Basically, the MCP server will only return if `is_gwas_significant` is `True`.

#### Get region-trait associations *(uses GWAS Summary Statistics API)*

| Parameter   | Type   | Required | Description                                 | Example        |
|-------------|--------|----------|---------------------------------------------|----------------|
| chromosome  | str    | Yes      | Chromosome (e.g., "1")                      | "1"            |
| start       | int    | Yes      | Start position (base-pair)                  | 1000000        |
| end         | int    | Yes      | End position (base-pair)                    | 2000000        |
| efo_id      | str    | Yes      | EFO trait identifier                        | "EFO_0008531"  |
| ...common   |        |          | See common parameters above                 |                |

> **Note:** Endpoints marked as "uses GWAS Summary Statistics API" access `https://www.ebi.ac.uk/gwas/summary-statistics/api` instead of the main REST API.

### Output Format

All API responses follow a consistent structure:

```json
{
  "request_url": "https://www.ebi.ac.uk/gwas/rest/api/...",
  "items": [...],  // List of results, limited by max_items_in_memory
  "total_items_aft_process": 123,  // Total number of results after processing
  "is_complete": true,  // Whether all results are included in items
  "metadata": {
    "subset_size": 100,  // Number of items in the current response (after using max_items_in_memory parameter)
    "max_items_in_memory": 5000,  // Current memory threshold
    "total_items": 150,  // Total number of items before processing
    "significant_items": 80  // Number of genome-wide significant items (if applicable)
  }
}
```

#### Large Result Sets

When results exceed `max_items_in_memory`:
1. A subset of results is returned in the `items` field
2. `is_complete` will be `False`
3. The complete dataset is automatically saved to a file
4. The response includes an `output_file` field with the file path

Example large result response:
```json
{
  "request_url": "...",
  "items": [...],  // First max_items_in_memory results
  "total_items_aft_process": 10000,
  "is_complete": false,
  "metadata": {
    "subset_size": 5000,
    "max_items_in_memory": 5000,
    "total_items": 12000,  // Original number of items
    "significant_items": 8000,  // Number of genome-wide significant items
    "output_file": "/tmp/large_result_abc123.json"
  }
}
```

> **IMPORTANT:** 
> - Always check the `is_complete` and `output_file` fields. If `is_complete` is `false`, only a subset of results is in `items` and the full result is saved to the file specified by `output_file`.
> - For endpoints that process p-values (e.g., associations), `total_items` represents the original count, while `total_items_aft_process` represents the count after filtering.
> - Study-related endpoints do not include p-value related metadata (`significant_items`).

#### Special Output Notes
- `get_trait_associations` may return a list of association IDs or, if the response format is unexpected, the raw association data structure.
- Some endpoints (notably those using the summary-statistics API) may return a single object in `items` if only one result is found.

## Credits

This tool relies on the [GWAS Catalog REST API](https://www.ebi.ac.uk/gwas/rest/docs/api) and [GWAS Summary Statistics API](https://www.ebi.ac.uk/gwas/summary-statistics/docs/api).

Please cite and credit the GWAS Catalog and each study when using this tool in your work.

## License

This MCP server itself is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

This project uses the GWAS Catalog REST API and data provided by EMBL-EBI. Please ensure you cite the GWAS Catalog and the original studies when using this tool or its outputs. See the GWAS Catalog Terms of Use for details.

## Acknowledgements

- [GWAS Catalog](https://www.ebi.ac.uk/gwas/)
- [FastMCP](https://github.com/jlowin/fastmcp)
