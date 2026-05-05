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


def test_rank_flights_empty_df():
    from flight_value_checker.rank import rank_flights
    ranked = rank_flights(_cleaned(), origin="ITH", destination="MIA", top_n=5)
    assert ranked.empty


def test_find_connecting_routes_direct_only():
    from flight_value_checker.rank import find_connecting_routes
    routes = find_connecting_routes(_cleaned(), origin="JFK", destination="LAX", max_stops=0, top_n=5)
    assert not routes.empty
    assert all(routes["n_stops"] == 0)
    assert "path" in routes.columns
    assert "value_score" in routes.columns


def test_find_connecting_routes_with_stops():
    from flight_value_checker.rank import find_connecting_routes
    routes = find_connecting_routes(_cleaned(), origin="JFK", destination="LAX", max_stops=1, top_n=10)
    assert not routes.empty
    assert "path_label" in routes.columns
    assert "on_time_rate" in routes.columns
    assert "total_duration_min" in routes.columns


def test_find_connecting_routes_same_origin_destination_raises():
    import pytest
    from flight_value_checker.rank import find_connecting_routes
    with pytest.raises(ValueError, match="Origin and destination must differ"):
        find_connecting_routes(_cleaned(), origin="JFK", destination="JFK", max_stops=1)


def test_find_connecting_routes_negative_stops_raises():
    import pytest
    from flight_value_checker.rank import find_connecting_routes
    with pytest.raises(ValueError, match="must be non-negative"):
        find_connecting_routes(_cleaned(), origin="JFK", destination="LAX", max_stops=-1)


def test_find_connecting_routes_too_many_stops_raises():
    import pytest
    from flight_value_checker.rank import find_connecting_routes
    with pytest.raises(ValueError, match="not supported"):
        find_connecting_routes(_cleaned(), origin="JFK", destination="LAX", max_stops=5)


def test_find_connecting_routes_custom_weights():
    from flight_value_checker.rank import find_connecting_routes
    routes = find_connecting_routes(
        _cleaned(),
        origin="JFK",
        destination="LAX",
        max_stops=1,
        weights={"duration": 0.7, "delay": 0.3}
    )
    assert not routes.empty
    assert "value_score" in routes.columns


def test_find_connecting_routes_no_path_exists():
    from flight_value_checker.rank import find_connecting_routes
    # Route that likely doesn't exist in fixture
    routes = find_connecting_routes(_cleaned(), origin="JFK", destination="XXX", max_stops=1)
    assert routes.empty


def test_aggregate_legs_empty_df():
    import pandas as pd
    from flight_value_checker.rank import _aggregate_legs
    result = _aggregate_legs(pd.DataFrame())
    assert result.empty
    assert "origin" in result.columns
    assert "destination" in result.columns


def test_aggregate_legs_filters_min_samples():
    from flight_value_checker.rank import _aggregate_legs
    result = _aggregate_legs(_cleaned(), min_samples=100)
    # With high min_samples, should filter out some routes
    assert "sample_size" in result.columns
    if not result.empty:
        assert (result["sample_size"] >= 100).all()


def test_minmax_constant_values():
    import pandas as pd
    from flight_value_checker.rank import _minmax
    series = pd.Series([5, 5, 5, 5])
    result = _minmax(series)
    assert (result == 0.0).all()


def test_minmax_normal_range():
    import pandas as pd
    from flight_value_checker.rank import _minmax
    series = pd.Series([0, 50, 100])
    result = _minmax(series)
    assert result.iloc[0] == 0.0
    assert result.iloc[2] == 1.0
    assert 0 <= result.iloc[1] <= 1


def test_score_flights_custom_weights():
    weights = {"delay": 0.5, "duration": 0.3, "price": 0.2}
    scored = score_flights(_cleaned(), weights=weights)
    assert "value_score" in scored.columns


def test_rank_carrier_options_with_price_filter():
    ranked = rank_carrier_options(_cleaned(), origin="JFK", destination="LAX", max_price=200)
    assert not ranked.empty
