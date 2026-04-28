from pathlib import Path

import pandas as pd
import pytest

from flight_value_checker.ingest import load_flight_data, save_processed_data

FIXTURE = Path(__file__).parent / "fixtures" / "sample_flights.csv"


def test_load_flight_data_reads_csv():
    df = load_flight_data(FIXTURE)
    assert len(df) == 8
    assert "ORIGIN" in df.columns


def test_load_flight_data_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        load_flight_data("not_here.csv")


def test_save_processed_data_writes_csv(tmp_path):
    out = tmp_path / "processed.csv"
    saved = save_processed_data(pd.DataFrame({"a": [1]}), out)
    assert saved.exists()
    assert pd.read_csv(saved).loc[0, "a"] == 1


def test_load_flight_data_rejects_unsupported_extension(tmp_path):
    bad = tmp_path / "flights.txt"
    bad.write_text("hello", encoding="utf-8")
    with pytest.raises(ValueError):
        load_flight_data(bad)


def test_save_processed_data_rejects_unsupported_extension(tmp_path):
    with pytest.raises(ValueError):
        save_processed_data(pd.DataFrame({"a": [1]}), tmp_path / "out.txt")


def test_download_file_rejects_non_http_scheme():
    from flight_value_checker.ingest import download_file

    with pytest.raises(ValueError):
        download_file("ftp://example.com/file.csv", "out.csv")
