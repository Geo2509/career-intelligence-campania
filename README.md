# Career Intelligence Campania

Python workflow for discovering and validating potential employers in Campania for direct job applications.

## What it does

1. Generates targeted search queries by role and location.
2. Collects candidate company websites from public search results.
3. Removes job boards and duplicate domains.
4. Profiles company websites for contact and careers information.
5. Classifies employer characteristics and role fit.
6. Applies rule-based qualification and scoring.
7. Exports structured results to JSON, CSV and XLSX.

## Data-processing focus

The project demonstrates web-data collection, cleaning, deduplication, validation, classification and structured spreadsheet export. It is complementary to `job-intelligence`: this repository focuses on employers, while `job-intelligence` focuses on published vacancies.

## Main tools

Python, Pandas, Requests, BeautifulSoup, DDGS, PyYAML and openpyxl.

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Example

```bash
python -m src.main --limit-queries 10 --output output/campania_targets
```

A search-only run is also available:

```bash
python -m src.main --limit-queries 10 --no-profile --output output/campania_targets
```

## Validation

```bash
python3 -m pytest
python3 -m compileall src tests
```

Runtime reports, local environments and secrets are excluded from Git.
