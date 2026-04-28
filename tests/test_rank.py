from pathlib import Path

from flight_value_checker.clean import clean_flight_data
from flight_value_checker.ingest import load_flight_data
from flight_value_checker.rank import filter_flights, rank_carrier_options, rank_flights, score_flights

FIXTURE = Path(__file__).parent / "fixtures" / "sample_flights.csv"


def _cleaned():
    return clean_flight_data(load_flight_data(FIXTURE))


def test_filter_flights_by_route_and_price():
    filtered = filter_flights(_cleaned(), origin="jfk", destination="lax", max_price=225)
    assert set(filtered["origin"]) == {"JFK"}
    assert set(filtered["destination"]) == {"LAX"}
    assert filtered["price_usd"].max() <= 225


def test_score_flights_adds_value_score():
    scored = score_flights(_cleaned())
    assert "value_score" in scored.columns
    assert scored["value_score"].between(0, 1).all()


def test_rank_flights_returns_best_rows():
    ranked = rank_flights(_cleaned(), origin="JFK", destination="LAX", top_n=3)
    assert len(ranked) == 3
    assert ranked["value_score"].is_monotonic_increasing


def test_rank_carrier_options_aggregates_by_airline():
    ranked = rank_carrier_options(_cleaned(), origin="JFK", destination="LAX")
    assert {"airline", "avg_duration_min", "on_time_rate", "sample_size", "value_score"}.issubset(ranked.columns)
    assert ranked["value_score"].is_monotonic_increasing


def test_score_flights_empty_returns_empty():
    empty = _cleaned().iloc[0:0]
    scored = score_flights(empty)
    assert scored.empty


def test_filter_flights_by_preferred_airline():
    filtered = filter_flights(_cleaned(), origin="JFK", destination="LAX", preferred_airline="DL")
    assert set(filtered["airline"]) == {"DL"}


def test_rank_carrier_options_no_matching_route_returns_empty():
    ranked = rank_carrier_options(_cleaned(), origin="ITH", destination="LAX")
    assert ranked.empty
