"""Filtering, scoring, and ranking logic for flight options."""

from __future__ import annotations

from collections.abc import Mapping

import pandas as pd

DEFAULT_WEIGHTS_WITH_PRICE = {"delay": 0.40, "duration": 0.25, "price": 0.35}
DEFAULT_WEIGHTS_NO_PRICE = {"delay": 0.55, "duration": 0.45}

# Itinerary-level defaults for multi-leg routes
LAYOVER_MIN_PER_STOP = 60
DEFAULT_MIN_LEG_SAMPLES = 5
MAX_SUPPORTED_STOPS = 3


def filter_flights(
    df: pd.DataFrame,
    origin: str | None = None,
    destination: str | None = None,
    max_price: float | None = None,
    preferred_airline: str | None = None,
) -> pd.DataFrame:
    """Filter flight rows using user-facing search parameters."""
    filtered = df.copy()

    if origin:
        filtered = filtered[filtered["origin"].str.upper() == origin.upper()]
    if destination:
        filtered = filtered[filtered["destination"].str.upper() == destination.upper()]
    if max_price is not None and "price_usd" in filtered.columns:
        filtered = filtered[filtered["price_usd"] <= max_price]
    if preferred_airline:
        filtered = filtered[filtered["airline"].str.upper() == preferred_airline.upper()]

    return filtered.reset_index(drop=True)


def _minmax(series: pd.Series) -> pd.Series:
    """Min-max normalize a numeric Series, returning zeros when values are constant."""
    numeric = pd.to_numeric(series, errors="coerce")
    minimum = numeric.min()
    maximum = numeric.max()
    if pd.isna(minimum) or pd.isna(maximum) or maximum == minimum:
        return pd.Series(0.0, index=series.index)
    return (numeric - minimum) / (maximum - minimum)


def score_flights(df: pd.DataFrame, weights: Mapping[str, float] | None = None) -> pd.DataFrame:
    """Add a lower-is-better `value_score` to individual flight rows."""
    if df.empty:
        return df.copy()

    scored = df.copy()
    has_price = "price_usd" in scored.columns and scored["price_usd"].notna().any()
    active_weights = dict(weights or (DEFAULT_WEIGHTS_WITH_PRICE if has_price else DEFAULT_WEIGHTS_NO_PRICE))

    scored["delay_component"] = _minmax(scored["positive_arr_delay_min"])
    scored["duration_component"] = _minmax(scored["duration_min"])
    scored["value_score"] = (
        active_weights.get("delay", 0) * scored["delay_component"]
        + active_weights.get("duration", 0) * scored["duration_component"]
    )

    if has_price:
        scored["price_component"] = _minmax(scored["price_usd"])
        scored["value_score"] += active_weights.get("price", 0) * scored["price_component"]

    return scored


def rank_flights(
    df: pd.DataFrame,
    origin: str | None = None,
    destination: str | None = None,
    top_n: int = 10,
    max_price: float | None = None,
    preferred_airline: str | None = None,
) -> pd.DataFrame:
    """Return the top individual flight observations by value score."""
    filtered = filter_flights(df, origin, destination, max_price, preferred_airline)
    scored = score_flights(filtered)
    if scored.empty:
        return scored
    return scored.nsmallest(top_n, "value_score").reset_index(drop=True)


def rank_carrier_options(
    df: pd.DataFrame,
    origin: str,
    destination: str,
    top_n: int = 10,
    max_price: float | None = None,
) -> pd.DataFrame:
    """Rank airlines serving a route using aggregate reliability and duration.

    This is the strongest default for BTS-style historical data: rather than pretending
    the dataset gives live ticket prices, it asks which carriers have historically provided
    the best value on a route.
    """
    route = filter_flights(df, origin=origin, destination=destination, max_price=max_price)
    if route.empty:
        return route

    aggregations: dict[str, tuple[str, str]] = {
        "avg_duration_min": ("duration_min", "mean"),
        "avg_arr_delay_min": ("arr_delay_min", "mean"),
        "avg_positive_arr_delay_min": ("positive_arr_delay_min", "mean"),
        "on_time_rate": ("on_time", "mean"),
        "sample_size": ("airline", "size"),
    }
    if "price_usd" in route.columns and route["price_usd"].notna().any():
        aggregations["avg_price_usd"] = ("price_usd", "mean")

    grouped = (
        route.groupby(["origin", "destination", "airline"], as_index=False)
        .agg(**aggregations)
        .sort_values("sample_size", ascending=False)
        .reset_index(drop=True)
    )

    score_frame = grouped.rename(
        columns={
            "avg_duration_min": "duration_min",
            "avg_positive_arr_delay_min": "positive_arr_delay_min",
            "avg_price_usd": "price_usd",
        }
    )
    scored = score_flights(score_frame)

    ranked = grouped.copy()
    ranked["value_score"] = scored["value_score"].to_numpy()
    ranked = ranked.sort_values(
        ["value_score", "avg_duration_min", "avg_positive_arr_delay_min"],
        ascending=[True, True, True],
    )
    return ranked.head(top_n).reset_index(drop=True)


def _aggregate_legs(df: pd.DataFrame, min_samples: int = DEFAULT_MIN_LEG_SAMPLES) -> pd.DataFrame:
    """Build a per-route aggregation table used as the leg graph for routing."""
    if df.empty:
        return pd.DataFrame(
            columns=[
                "origin",
                "destination",
                "duration_min",
                "arr_delay_min",
                "positive_arr_delay_min",
                "on_time_rate",
                "sample_size",
            ]
        )

    legs = df.groupby(["origin", "destination"], as_index=False).agg(
        duration_min=("duration_min", "mean"),
        arr_delay_min=("arr_delay_min", "mean"),
        positive_arr_delay_min=("positive_arr_delay_min", "mean"),
        on_time_rate=("on_time", "mean"),
        sample_size=("airline", "size"),
    )
    return legs[legs["sample_size"] >= min_samples].reset_index(drop=True)


def _enumerate_paths(
    legs_df: pd.DataFrame, origin: str, destination: str, max_stops: int
) -> list[list[str]]:
    """DFS the leg graph for simple paths from origin to destination with <= max_stops stops."""
    graph: dict[str, list[str]] = {}
    for o, d in legs_df[["origin", "destination"]].itertuples(index=False):
        graph.setdefault(o, []).append(d)

    max_nodes = max_stops + 2
    all_paths: list[list[str]] = []

    def dfs(current: str, path: list[str]) -> None:
        if current == destination and len(path) >= 2:
            all_paths.append(path.copy())
            return
        if len(path) >= max_nodes:
            return
        for next_air in graph.get(current, []):
            if next_air in path:
                continue
            path.append(next_air)
            dfs(next_air, path)
            path.pop()

    dfs(origin, [origin])
    return all_paths


def _airlines_for_leg(df: pd.DataFrame, origin: str, destination: str) -> list[str]:
    """Return sorted list of airlines operating a specific direct leg."""
    mask = (df["origin"] == origin) & (df["destination"] == destination)
    return sorted(df.loc[mask, "airline"].unique().tolist())


def _score_paths(
    paths: list[list[str]],
    legs_df: pd.DataFrame,
    df: pd.DataFrame,
    weights: Mapping[str, float],
) -> pd.DataFrame:
    """Build an itinerary-level DataFrame with totals and a value score."""
    leg_lookup = legs_df.set_index(["origin", "destination"]).to_dict("index")

    rows = []
    for path in paths:
        legs = list(zip(path[:-1], path[1:]))
        leg_data = [leg_lookup[(o, d)] for (o, d) in legs]
        n_stops = len(path) - 2

        total_flight_min = sum(leg["duration_min"] for leg in leg_data)
        total_layover_min = n_stops * LAYOVER_MIN_PER_STOP
        total_duration_min = total_flight_min + total_layover_min
        total_positive_delay = sum(leg["positive_arr_delay_min"] for leg in leg_data)

        # Probability the whole journey is on-time = product of per-leg on-time rates
        on_time_rate = 1.0
        for leg in leg_data:
            on_time_rate *= float(leg["on_time_rate"])

        sample_size = min(int(leg["sample_size"]) for leg in leg_data)
        airlines_per_leg = [_airlines_for_leg(df, o, d) for (o, d) in legs]
        airline_label = " | ".join(",".join(a) for a in airlines_per_leg)

        rows.append(
            {
                "path": path,
                "path_label": " → ".join(path),
                "n_stops": n_stops,
                "n_legs": len(legs),
                "airlines_per_leg": airlines_per_leg,
                "airline_label": airline_label,
                "total_flight_min": total_flight_min,
                "total_layover_min": total_layover_min,
                "total_duration_min": total_duration_min,
                "total_positive_arr_delay_min": total_positive_delay,
                "on_time_rate": on_time_rate,
                "sample_size": sample_size,
            }
        )

    result = pd.DataFrame(rows)
    if result.empty:
        return result

    result["duration_component"] = _minmax(result["total_duration_min"])
    result["delay_component"] = _minmax(result["total_positive_arr_delay_min"])
    result["value_score"] = (
        weights.get("duration", 0) * result["duration_component"]
        + weights.get("delay", 0) * result["delay_component"]
    )

    return result.sort_values(
        ["n_stops", "value_score", "total_duration_min"],
        ascending=[True, True, True],
    ).reset_index(drop=True)


def find_connecting_routes(
    df: pd.DataFrame,
    origin: str,
    destination: str,
    max_stops: int = 1,
    top_n: int = 20,
    min_samples: int = DEFAULT_MIN_LEG_SAMPLES,
    weights: Mapping[str, float] | None = None,
) -> pd.DataFrame:
    """Rank itineraries from origin to destination with up to ``max_stops`` layovers.

    Parameters
    ----------
    df:
        Cleaned flight DataFrame (output of :func:`flight_value_checker.clean.clean_flight_data`).
    origin, destination:
        IATA airport codes.
    max_stops:
        Maximum allowed connecting stops (0 = direct only).
    top_n:
        Maximum itineraries to return (after sorting by stops then value score).
    min_samples:
        Minimum per-leg flight count before the leg is eligible to be in a path.
        Filters out tiny/seasonal routes that would skew aggregates.
    weights:
        Optional override for the duration/delay weights used in the value score.

    Returns
    -------
    DataFrame
        One row per ranked itinerary with columns including ``path``, ``path_label``,
        ``n_stops``, ``total_duration_min``, ``on_time_rate``, ``value_score``,
        ``sample_size``, and ``airlines_per_leg``.
    """
    if max_stops < 0:
        raise ValueError("max_stops must be non-negative.")
    if max_stops > MAX_SUPPORTED_STOPS:
        raise ValueError(
            f"max_stops > {MAX_SUPPORTED_STOPS} is not supported (search space explodes)."
        )

    origin = origin.strip().upper()
    destination = destination.strip().upper()
    if origin == destination:
        raise ValueError("Origin and destination must differ.")

    legs_df = _aggregate_legs(df, min_samples=min_samples)
    if legs_df.empty:
        return pd.DataFrame()

    paths = _enumerate_paths(legs_df, origin, destination, max_stops)
    if not paths:
        return pd.DataFrame()

    active_weights = dict(weights or {"duration": 0.6, "delay": 0.4})
    scored = _score_paths(paths, legs_df, df, active_weights)
    return scored.head(top_n).reset_index(drop=True)
