# Flight Value Checker

A GitHub-ready ORIE 5270 computational project that ranks flight options using real flight performance data. The package ingests flight data, cleans it into a standard schema, ranks route/carrier options, creates interactive HTML charts, and builds a final HTML report.

## Project purpose

The goal is to build a reproducible "flight checker" that helps compare route options by historical reliability, travel time, and optionally price when price data is available. The main output is a ranked table plus HTML visualizations showing the cost/service-style trade-off across airlines.

## Dataset strategy

Recommended final dataset: Bureau of Transportation Statistics (BTS) Reporting Carrier On-Time Performance data.

Why BTS:
- It is a legitimate public flight dataset.
- It contains real U.S. flight observations, delays, cancellations, carriers, airports, dates, and elapsed times.
- It avoids fragile scraping of JavaScript-heavy travel sites.

Optional extension: add an Amadeus API adapter later for live price quotes. The core project does not use this, because API keys and quotas can be a headache.

## Install

From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate   # Windows PowerShell
pip install -e ".[dev]"
```

## Run tests

```bash
pytest
```

The `pyproject.toml` configuration requires at least 80% coverage.

## Data setup

Download a BTS on-time performance CSV and place it at:

```text
data/raw/bts_flights.csv
```

The project expects columns such as `FL_DATE`, `OP_UNIQUE_CARRIER`, `ORIGIN`, `DEST`, `ACTUAL_ELAPSED_TIME`, `ARR_DELAY`, `DEP_DELAY`, `DISTANCE`, `CANCELLED`, and `DIVERTED`. A `PRICE` or `price_usd` column is optional.

## Run the full pipeline

Using the console command:

```bash
flight-checker --input data/raw/bts_flights.csv --origin JFK --destination LAX --top-n 10
```

Or using the convenience script:

```bash
python scripts/run_analysis.py --input data/raw/bts_flights.csv --origin JFK --destination LAX --top-n 10
```

Outputs:

```text
data/processed/clean_flights.csv
docs/report.html
docs/assets/value_score_by_airline.html
docs/assets/on_time_rate_by_airline.html
docs/assets/duration_delay_tradeoff.html
```

## Package structure

```text
flight-value-checker/
├── pyproject.toml
├── README.md
├── data/
│   ├── raw/
│   └── processed/
├── docs/
│   └── assets/
├── scripts/
│   └── run_analysis.py
├── src/
│   └── flight_value_checker/
│       ├── __init__.py
│       ├── ingest.py
│       ├── clean.py
│       ├── rank.py
│       ├── visualize.py
│       ├── report.py
│       ├── scrape_static.py
│       └── cli.py
└── tests/
```

## Main modules

- `ingest.py`: load CSV/Parquet files and save processed datasets.
- `clean.py`: standardize BTS-style columns, remove canceled/diverted flights, and create reliability features.
- `rank.py`: filter flights and rank individual or aggregated route options.
- `visualize.py`: create interactive Plotly HTML charts.
- `report.py`: build the final report.
- `scrape_static.py`: safe static HTML parser for permitted/mock pages only.
- `cli.py`: command-line interface.

## Performance notes

The ranking pipeline uses vectorized pandas operations rather than Python row loops. Route filtering uses boolean masks, aggregation uses `groupby`, and top-N ranking uses `nsmallest`, which avoids fully sorting more data than necessary for individual flight ranking. For larger BTS files, consider loading only needed columns, saving cleaned data as Parquet, and using categorical dtypes for airport and airline columns.

## Minimum viable project

A strong MVP is:

1. Installable package with `pip install -e ".[dev]"`.
2. BTS CSV ingestion.
3. Cleaning and route filtering.
4. Carrier ranking for one route, such as JFK to LAX.
5. Three Plotly HTML visualizations.
6. Final `docs/report.html`.
7. Unit tests above 80% coverage.
8. README with install, run, data, and interpretation instructions.
