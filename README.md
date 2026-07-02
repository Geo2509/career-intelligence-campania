# Career Intelligence Campania

`career-intelligence-campania` finds companies in Campania that may be worth contacting directly, even when they do not have an open job ad.

It is intentionally separate from `job-intelligence`:

- `job-intelligence` = where open jobs are published
- `career-intelligence-campania` = which employers to contact directly

The old project is only a reference for patterns such as DuckDuckGo discovery, cleaning/deduplication, Excel export, and history handling. This repository should not become a clone of it.

## Current Pipeline

1. Generate search queries from roles, locations, and intent templates.
2. Run enabled search engines.
3. Extract likely company websites from search results.
4. Remove job boards and duplicate domains.
5. Optionally profile company websites for emails, phones, contact pages, and careers pages.
6. Score companies by role fit, location fit, and direct contact signals.
7. Export JSON, CSV, and XLSX files.

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Usage

Small full discovery run:

```bash
python -m src.main --limit-queries 10 --output output/campania_targets
```

Fast search-only run:

```bash
python -m src.main --limit-queries 10 --no-profile --output output/campania_targets
```

SerpAPI is configured but disabled by default. To use it, enable `serpapi` in `configs/search_engines.yaml` and set:

```bash
export SERPAPI_API_KEY=...
```

## Tests

```bash
python3 -m pytest
python3 -m compileall src tests
```
