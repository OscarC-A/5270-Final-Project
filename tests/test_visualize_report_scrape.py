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


def test_lookup_airport_found():
    import pandas as pd
    from flight_value_checker.visualize import _lookup_airport
    airports = pd.DataFrame({
        "iata_code": ["JFK", "LAX"],
        "name": ["John F Kennedy Intl", "Los Angeles Intl"],
        "latitude_deg": [40.6398, 33.9425],
        "longitude_deg": [-73.7789, -118.408]
    })
    result = _lookup_airport(airports, "JFK")
    assert result["iata"] == "JFK"
    assert result["name"] == "John F Kennedy Intl"
    assert result["lat"] == 40.6398
    assert result["lon"] == -73.7789


def test_lookup_airport_case_insensitive():
    import pandas as pd
    from flight_value_checker.visualize import _lookup_airport
    airports = pd.DataFrame({
        "iata_code": ["JFK"],
        "name": ["John F Kennedy Intl"],
        "latitude_deg": [40.6398],
        "longitude_deg": [-73.7789]
    })
    result = _lookup_airport(airports, "jfk")
    assert result["iata"] == "JFK"


def test_lookup_airport_not_found():
    import pandas as pd
    import pytest
    from flight_value_checker.visualize import _lookup_airport
    airports = pd.DataFrame({
        "iata_code": ["JFK"],
        "name": ["John F Kennedy Intl"],
        "latitude_deg": [40.6398],
        "longitude_deg": [-73.7789]
    })
    with pytest.raises(ValueError, match="not found"):
        _lookup_airport(airports, "XXX")


def test_plot_flight_path(tmp_path):
    import pandas as pd
    from flight_value_checker.visualize import plot_flight_path
    airports = pd.DataFrame({
        "iata_code": ["JFK", "LAX"],
        "name": ["John F Kennedy Intl", "Los Angeles Intl"],
        "latitude_deg": [40.6398, 33.9425],
        "longitude_deg": [-73.7789, -118.408]
    })
    result = plot_flight_path("JFK", "LAX", airports, tmp_path)
    assert result.exists()
    assert result.name == "flight_path_JFK_LAX.html"
    html = result.read_text()
    # HTML may contain unicode arrow or encoded version
    assert ("JFK" in html and "LAX" in html) or "Flight Path" in html


def test_plot_live_flights(tmp_path):
    import pandas as pd
    from flight_value_checker.visualize import plot_live_flights
    airports = pd.DataFrame({
        "iata_code": ["JFK", "LAX"],
        "name": ["John F Kennedy Intl", "Los Angeles Intl"],
        "latitude_deg": [40.6398, 33.9425],
        "longitude_deg": [-73.7789, -118.408]
    })
    # This test may or may not fetch live data depending on API availability
    result = plot_live_flights("JFK", "LAX", airports, tmp_path)
    assert result.exists()
    assert result.name == "live_flights_JFK_LAX.html"
    html = result.read_text()
    assert "Live Flights" in html


def test_plot_route_options(tmp_path):
    import pandas as pd
    from flight_value_checker.visualize import plot_route_options
    airports = pd.DataFrame({
        "iata_code": ["JFK", "LAX", "ORD"],
        "name": ["John F Kennedy Intl", "Los Angeles Intl", "O'Hare Intl"],
        "latitude_deg": [40.6398, 33.9425, 41.9742],
        "longitude_deg": [-73.7789, -118.408, -87.9073]
    })
    routes = pd.DataFrame({
        "path": [["JFK", "LAX"], ["JFK", "ORD", "LAX"]],
        "path_label": ["JFK → LAX", "JFK → ORD → LAX"],
        "n_stops": [0, 1],
        "value_score": [0.5, 0.7]
    })
    result = plot_route_options(routes, airports, tmp_path, "JFK", "LAX", top_n=2)
    assert result.exists()
    assert result.name == "route_options_JFK_LAX.html"
    html = result.read_text()
    assert "Route Options" in html


def test_plot_route_options_empty_raises(tmp_path):
    import pandas as pd
    import pytest
    from flight_value_checker.visualize import plot_route_options
    airports = pd.DataFrame({
        "iata_code": ["JFK"],
        "name": ["John F Kennedy Intl"],
        "latitude_deg": [40.6398],
        "longitude_deg": [-73.7789]
    })
    with pytest.raises(ValueError, match="empty route options"):
        plot_route_options(pd.DataFrame(), airports, tmp_path, "JFK", "LAX")
