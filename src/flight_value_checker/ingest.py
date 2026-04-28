"""Data ingestion utilities for flight datasets.

The final project is designed around reproducible CSV/Parquet files such as the
Bureau of Transportation Statistics on-time performance data. Keeping ingestion
separate from cleaning makes it easy to unit test and swap data sources later.
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlretrieve

import pandas as pd


def load_flight_data(path: str | Path) -> pd.DataFrame:
    """Load a flight dataset from CSV or Parquet.

    Parameters
    ----------
    path:
        Local path to a `.csv` or `.parquet` file.

    Returns
    -------
    pandas.DataFrame
        Raw flight records.

    Raises
    ------
    FileNotFoundError
        If the path does not exist.
    ValueError
        If the file type is not supported.
    """
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Flight data file not found: {file_path}")

    suffix = file_path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(file_path, low_memory=False)
    if suffix == ".parquet":
        return pd.read_parquet(file_path)

    raise ValueError(f"Unsupported file type '{suffix}'. Use .csv or .parquet.")


def save_processed_data(df: pd.DataFrame, path: str | Path) -> Path:
    """Save a processed DataFrame to CSV or Parquet and return the output path."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    suffix = output_path.suffix.lower()
    if suffix == ".csv":
        df.to_csv(output_path, index=False)
    elif suffix == ".parquet":
        df.to_parquet(output_path, index=False)
    else:
        raise ValueError(f"Unsupported file type '{suffix}'. Use .csv or .parquet.")

    return output_path


OURAIRPORTS_URL = (
    "https://davidmegginson.github.io/ourairports-data/airports.csv"
)


def load_airports(path: str | Path | None = None) -> pd.DataFrame:
    """Load the OurAirports airports.csv into a DataFrame.

    If *path* is None, downloads the file from OurAirports and caches it at
    ``data/raw/airports.csv``.  The file is only re-downloaded when missing.

    Columns of interest: ``iata_code``, ``name``, ``latitude_deg``, ``longitude_deg``.
    Rows without a valid IATA code are dropped.
    """
    if path is None:
        cached = Path("data/raw/airports.csv")
        download_file(OURAIRPORTS_URL, cached, overwrite=False)
        path = cached

    df = pd.read_csv(path, low_memory=False)
    df.columns = [c.strip().lower() for c in df.columns]
    df = df[df["iata_code"].notna() & (df["iata_code"].astype(str).str.strip() != "")]
    return df.reset_index(drop=True)


def download_file(url: str, output_path: str | Path, overwrite: bool = False) -> Path:
    """Download a public data file to a local path.

    This is intentionally simple and meant for public, permitted datasets only.
    It is not intended for scraping protected or JavaScript-heavy travel sites.
    """
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("Only http and https URLs are supported.")

    output = Path(output_path)
    if output.exists() and not overwrite:
        return output

    output.parent.mkdir(parents=True, exist_ok=True)
    urlretrieve(url, output)  # noqa: S310 - user-provided URL for public datasets
    return output
