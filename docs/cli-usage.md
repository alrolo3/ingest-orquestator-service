# CLI Usage Reference

The CLI entry point is available through Python module execution:

```bash
python -m ingest_orquestator_server.cli [OPTIONS] COMMAND [ARGS]...
```

After installing the package, the project script can also be used:

```bash
ingest-orquestator [OPTIONS] COMMAND [ARGS]...
```

All commands read the same `INGEST_` environment variables described in
[environment-config.md](environment-config.md). CLI options override the
corresponding environment/profile setting for the current command only.

## Global Options

| Option | Explanation |
| --- | --- |
| `--install-completion` | Installs shell completion for the current shell. Provided by Typer. |
| `--show-completion` | Prints shell completion configuration. Provided by Typer. |
| `--help` | Shows command help. |

## Commands

| Command | Purpose |
| --- | --- |
| `parse` | Parse one file and write document artifacts. |
| `batch` | Parse many files or all supported files below one or more directories. |
| `benchmark` | Run one or more pipelines against files and write benchmark JSON/Markdown. |
| `cleanup` | Delete or preview deletion of old local artifacts and jobs. |

## `parse`

Parse one file.

```bash
python -m ingest_orquestator_server.cli parse FILE [OPTIONS]
```

Example:

```bash
python -m ingest_orquestator_server.cli parse sample-inputs/sample.pdf \
  --parser docling \
  --pipeline standard \
  --profile rag_ready \
  --output-dir .data/outputs
```

### Arguments

| Argument | Required | Explanation |
| --- | --- | --- |
| `FILE` | Yes | Existing readable file to parse. Directories are not accepted by `parse`; use `batch` for directories. |

### Options

| Option | Default | Explanation |
| --- | --- | --- |
| `--output-dir`, `-o` | `INGEST_STORAGE_DIR/outputs` | Directory where output artifacts are written. Each parse creates a document-specific subdirectory. |
| `--parser`, `-p` | `docling` | Parser backend. Currently supported value: `docling`. |
| `--pipeline` | `INGEST_DOCLING_PIPELINE` | Docling pipeline for this parse. Valid values: `standard`, `vlm`, `auto`. `vlm` is PDF/image only. |
| `--profile` | `INGEST_PROFILE` | Ingestion profile. Valid values: `rag_ready`, `parse_only`, `ocr_only`, `standard_enriched`, `vlm`. |
| `--chunking` / `--no-chunking` | Profile/config value | Overrides chunk generation for this parse. `--no-chunking` also prevents embedding records because embedding records are built from chunks. |
| `--chunking-strategy` | Profile/config value | Overrides chunking strategy. Valid values: `hybrid`, `line_based`, `legacy_char`. |
| `--help` | - | Shows command help. |

### Output

The command prints JSON with document metadata, counts, diagnostics metadata, and
artifact paths. A successful parse can include:

```text
raw_docling.json
normalized.json
document.md
document.txt
document.html
chunks.json
embedding_input.jsonl
confidence.json
manifest.json
```

## `batch`

Parse many files or recursively parse supported files inside directories.

```bash
python -m ingest_orquestator_server.cli batch INPUTS... [OPTIONS]
```

Example:

```bash
python -m ingest_orquestator_server.cli batch sample-inputs \
  --parser docling \
  --pipeline standard \
  --profile rag_ready \
  --output-dir .data/outputs
```

### Arguments

| Argument | Required | Explanation |
| --- | --- | --- |
| `INPUTS...` | Yes | One or more readable files or directories. Directories are searched recursively for files whose extensions are allowed by `INGEST_ALLOWED_UPLOAD_EXTENSIONS`. |

### Options

| Option | Default | Explanation |
| --- | --- | --- |
| `--output-dir`, `-o` | `INGEST_STORAGE_DIR/outputs` | Directory where output artifacts are written. Each parsed document gets its own subdirectory. |
| `--parser`, `-p` | `docling` | Parser backend. Currently supported value: `docling`. |
| `--pipeline` | `INGEST_DOCLING_PIPELINE` | Docling pipeline for every file in the batch. Valid values: `standard`, `vlm`, `auto`. `vlm` fails validation for non-PDF/image inputs. |
| `--profile` | `INGEST_PROFILE` | Ingestion profile applied to every file in the batch. |
| `--chunking` / `--no-chunking` | Profile/config value | Overrides chunk generation for every file in the batch. |
| `--chunking-strategy` | Profile/config value | Overrides chunking strategy for every file in the batch. Valid values: `hybrid`, `line_based`, `legacy_char`. |
| `--help` | - | Shows command help. |

### Output

The command prints JSON with:

| Field | Explanation |
| --- | --- |
| `file_count` | Number of input files selected for parsing. |
| `processed_count` | Number of parse results returned. |
| `successful_count` | Number of results with Docling status `success` or `partial_success`. |
| `failed_count` | Number of results not considered successful. |
| `results` | Per-document result objects containing status, counts, metadata, and output paths. |

## `benchmark`

Run benchmark parses for one or more files and one or more pipelines.

```bash
python -m ingest_orquestator_server.cli benchmark FILES... [OPTIONS]
```

Example:

```bash
python -m ingest_orquestator_server.cli benchmark sample-inputs/sample.pdf \
  --pipelines standard,vlm \
  --profile rag_ready \
  --output-dir .data/benchmarks
```

### Arguments

| Argument | Required | Explanation |
| --- | --- | --- |
| `FILES...` | Yes | Existing readable files to benchmark. Directories are not accepted by `benchmark`. |

### Options

| Option | Default | Explanation |
| --- | --- | --- |
| `--output-dir`, `-o` | `INGEST_STORAGE_DIR/benchmarks` | Directory where benchmark run directories are written. Each run uses a UTC timestamp subdirectory. |
| `--parser`, `-p` | `docling` | Parser backend. Currently supported value: `docling`. |
| `--pipelines` | `standard` | Comma-separated pipelines to run for each file, for example `standard,vlm`. Valid pipeline values are `standard`, `vlm`, and `auto`. |
| `--profile` | `INGEST_PROFILE` | Ingestion profile applied to each benchmark parse. |
| `--chunking` / `--no-chunking` | Profile/config value | Overrides chunk generation for each benchmark parse. |
| `--chunking-strategy` | Profile/config value | Overrides chunking strategy for each benchmark parse. Valid values: `hybrid`, `line_based`, `legacy_char`. |
| `--help` | - | Shows command help. |

### Output

The command writes:

| File | Explanation |
| --- | --- |
| `benchmark.json` | Machine-readable benchmark results with duration, counts, confidence summary, warnings, outputs, and per-run metadata. |
| `benchmark.md` | Markdown table summarizing file, pipeline, status, duration, pages, elements, chunks, confidence, and warnings. |

It also prints the same benchmark summary JSON to stdout.

## `cleanup`

Preview or delete old local artifacts.

```bash
python -m ingest_orquestator_server.cli cleanup [OPTIONS]
```

Examples:

```bash
python -m ingest_orquestator_server.cli cleanup --older-than-days 30 --dry-run
python -m ingest_orquestator_server.cli cleanup --older-than-days 30 --delete
```

### Options

| Option | Default | Explanation |
| --- | --- | --- |
| `--older-than-days` | `INGEST_RETENTION_DAYS` | Deletes or previews artifacts older than this many days. |
| `--dry-run` / `--delete` | `--dry-run` | `--dry-run` reports what would be deleted. `--delete` performs deletion. |
| `--help` | - | Shows command help. |

### Output

The command prints JSON with:

| Field | Explanation |
| --- | --- |
| `dry_run` | Whether the cleanup was a preview. |
| `cutoff` | Timestamp cutoff used for retention. |
| `deleted_paths` | Paths deleted when `--delete` is used. Empty for dry runs. |
| `skipped_paths` | Paths that matched cleanup scanning but were skipped. |

## Common Recipes

CPU parse with the CPU profile:

```bash
set -a
source env-cpu
set +a

python -m ingest_orquestator_server.cli parse sample-inputs/sample.pdf \
  --pipeline standard \
  --profile rag_ready
```

GPU enriched parse:

```bash
set -a
source env-cuda-gpu
set +a

python -m ingest_orquestator_server.cli parse sample-inputs/qwen3-picture-description-smoke.pdf \
  --pipeline standard \
  --profile standard_enriched
```

Full VLM parse for a PDF:

```bash
set -a
source env-cuda-gpu
set +a

python -m ingest_orquestator_server.cli parse sample-inputs/sample.pdf \
  --pipeline vlm \
  --profile vlm
```

Batch parse all sample inputs:

```bash
python -m ingest_orquestator_server.cli batch sample-inputs \
  --pipeline standard \
  --profile rag_ready \
  --output-dir .data/outputs
```
