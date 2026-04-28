"""Filtering, scoring, and ranking logic for flight options."""

from __future__ import annotations

from collections.abc import Mapping

import pandas as pd

DEFAULT_WEIGHTS_WITH_PRICE = {"delay": 0.40, "duration": 0.25, "price": 0.35}
DEFAULT_WEIGHTS_NO_PRICE = {"delay": 0.55, "duration": 0.45}


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
