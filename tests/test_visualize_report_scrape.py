from pathlib import Path

from flight_value_checker.clean import clean_flight_data
from flight_value_checker.ingest import load_flight_data
from flight_value_checker.rank import rank_carrier_options
from flight_value_checker.report import build_html_report
from flight_value_checker.scrape_static import parse_static_flight_cards
from flight_value_checker.visualize import create_visualizations

FIXTURE = Path(__file__).parent / "fixtures" / "sample_flights.csv"


def _ranked():
    cleaned = clean_flight_data(load_flight_data(FIXTURE))
    return rank_carrier_options(cleaned, origin="JFK", destination="LAX")


def test_create_visualizations_writes_html_files(tmp_path):
    charts = create_visualizations(_ranked(), tmp_path)
    assert set(charts) == {"value_score", "on_time_rate", "duration_delay_tradeoff"}
    assert all(path.exists() for path in charts.values())


def test_build_html_report_writes_rankings(tmp_path):
    chart = tmp_path / "chart.html"
    chart.write_text("<html></html>", encoding="utf-8")
    report = build_html_report(_ranked(), {"chart": chart}, tmp_path / "report.html")
    html = report.read_text(encoding="utf-8")
    assert "Flight Value Checker Report" in html
    assert "Ranked Route Options" in html
    assert "DL" in html


def test_parse_static_flight_cards():
    html = """
    <div class="flight-card" data-origin="JFK" data-destination="LAX"
         data-airline="DL" data-duration-min="370" data-price-usd="250"></div>
    """
    parsed = parse_static_flight_cards(html)
    assert len(parsed) == 1
    assert parsed.loc[0, "origin"] == "JFK"
    assert parsed.loc[0, "price_usd"] == "250"


def test_create_visualizations_rejects_empty_table(tmp_path):
    import pandas as pd
    import pytest

    with pytest.raises(ValueError):
        create_visualizations(pd.DataFrame(), tmp_path)


def test_parse_static_flight_cards_ignores_incomplete_cards():
    html = '<div class="flight-card" data-origin="JFK"></div>'
    parsed = parse_static_flight_cards(html)
    assert parsed.empty
