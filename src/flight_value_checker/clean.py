"""Cleaning and schema-standardization functions for flight data."""

from __future__ import annotations

import pandas as pd

COLUMN_ALIASES = {
    # date
    "fl_date": "date",
    "flight_date": "date",
    "flightdate": "date",          # BTS camelCase after lowercasing
    "date": "date",
    # airline
    "op_unique_carrier": "airline",
    "reporting_airline": "airline",
    "iata_code_reporting_airline": "airline",  # BTS alternate
    "mkt_unique_carrier": "airline",
    "carrier": "airline",
    "airline": "airline",
    # airports
    "origin": "origin",
    "origin_airport": "origin",
    "dest": "destination",
    "destination": "destination",
    "destination_airport": "destination",
    # duration
    "actual_elapsed_time": "duration_min",
    "actualelapsedtime": "duration_min",       # BTS camelCase after lowercasing
    "crs_elapsed_time": "duration_min",
    "crselapsedtime": "duration_min",          # BTS camelCase after lowercasing
    "elapsed_time": "duration_min",
    "duration_min": "duration_min",
    # arrival delay
    "arr_delay": "arr_delay_min",
    "arrdelay": "arr_delay_min",               # BTS camelCase after lowercasing
    "arrival_delay": "arr_delay_min",
    "arr_delay_min": "arr_delay_min",
    # departure delay
    "dep_delay": "dep_delay_min",
    "depdelay": "dep_delay_min",               # BTS camelCase after lowercasing
    "departure_delay": "dep_delay_min",
    "dep_delay_min": "dep_delay_min",
    "distance": "distance_miles",
    "distance_miles": "distance_miles",
    "cancelled": "cancelled",
    "canceled": "cancelled",
    "diverted": "diverted",
    "price": "price_usd",
    "price_usd": "price_usd",
    "total_price": "price_usd",
}

REQUIRED_COLUMNS = {"origin", "destination", "airline", "duration_min", "arr_delay_min"}


def standardize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy with normalized column names and known aliases renamed."""
    renamed = df.copy()
    renamed.columns = [str(col).strip().lower() for col in renamed.columns]
    renamed = renamed.rename(columns={col: COLUMN_ALIASES[col] for col in renamed.columns if col in COLUMN_ALIASES})
    # Multiple source columns can map to the same target (e.g. both Reporting_Airline
    # and IATA_CODE_Reporting_Airline → airline). Keep the first occurrence.
    renamed = renamed.loc[:, ~renamed.columns.duplicated()]
    return renamed


def validate_required_columns(df: pd.DataFrame, required: set[str] | None = None) -> None:
    """Raise a helpful error if required standardized columns are missing."""
    required_cols = required or REQUIRED_COLUMNS
    missing = sorted(required_cols - set(df.columns))
    if missing:
        raise ValueError(f"Missing required standardized columns: {missing}")


def clean_flight_data(df: pd.DataFrame, drop_cancelled: bool = True) -> pd.DataFrame:
    """Clean raw flight records into a consistent schema.

    The output keeps one row per flight observation and adds useful columns:
    `positive_arr_delay_min`, `on_time`, and `value_time_min`.
    """
    cleaned = standardize_columns(df)
    validate_required_columns(cleaned)

    cleaned = cleaned.copy()
    if "date" in cleaned.columns:
        cleaned["date"] = pd.to_datetime(cleaned["date"], errors="coerce")

    for col in ["origin", "destination", "airline"]:
        cleaned[col] = cleaned[col].astype(str).str.strip().str.upper()

    numeric_columns = [
        "duration_min",
        "arr_delay_min",
        "dep_delay_min",
        "distance_miles",
        "cancelled",
        "diverted",
        "price_usd",
    ]
    for col in numeric_columns:
        if col in cleaned.columns:
            cleaned[col] = pd.to_numeric(cleaned[col], errors="coerce")

    if "cancelled" not in cleaned.columns:
        cleaned["cancelled"] = 0
    if "diverted" not in cleaned.columns:
        cleaned["diverted"] = 0

    if drop_cancelled:
        cleaned = cleaned[(cleaned["cancelled"].fillna(0) == 0) & (cleaned["diverted"].fillna(0) == 0)]

    cleaned = cleaned.dropna(subset=["origin", "destination", "airline", "duration_min", "arr_delay_min"])
    cleaned["positive_arr_delay_min"] = cleaned["arr_delay_min"].clip(lower=0)
    cleaned["on_time"] = cleaned["arr_delay_min"] <= 15
    cleaned["value_time_min"] = cleaned["duration_min"] + cleaned["positive_arr_delay_min"]

    return cleaned.reset_index(drop=True)
