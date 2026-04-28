from pathlib import Path

import pandas as pd
import pytest

from flight_value_checker.clean import clean_flight_data, standardize_columns, validate_required_columns
from flight_value_checker.ingest import load_flight_data

FIXTURE = Path(__file__).parent / "fixtures" / "sample_flights.csv"


def test_standardize_columns_maps_bts_names():
    raw = load_flight_data(FIXTURE)
    standardized = standardize_columns(raw)
    assert {"date", "airline", "destination", "duration_min", "arr_delay_min"}.issubset(standardized.columns)


def test_clean_flight_data_drops_cancelled_and_adds_features():
    raw = load_flight_data(FIXTURE)
    cleaned = clean_flight_data(raw)
    assert len(cleaned) == 7
    assert cleaned["origin"].str.isupper().all()
    assert "on_time" in cleaned.columns
    assert "value_time_min" in cleaned.columns
    assert cleaned.loc[cleaned["arr_delay_min"] < 0, "positive_arr_delay_min"].eq(0).all()


def test_validate_required_columns_raises_for_missing_schema():
    with pytest.raises(ValueError):
        validate_required_columns(pd.DataFrame({"origin": ["JFK"]}))
