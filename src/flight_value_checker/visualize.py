"""Visualization helpers for flight rankings and route maps."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


def _lookup_airport(airports: pd.DataFrame, code: str) -> dict:
    """Return lat/lon/name for an IATA code from an airports lookup DataFrame."""
    code = code.strip().upper()
    match = airports[airports["iata_code"].str.upper() == code]
    if match.empty:
        raise ValueError(f"Airport code '{code}' not found in airports dataset.")
    row = match.iloc[0]
    return {
        "iata": code,
        "name": str(row.get("name", code)),
        "lat": float(row["latitude_deg"]),
        "lon": float(row["longitude_deg"]),
    }


def plot_flight_path(
    origin: str,
    destination: str,
    airports: pd.DataFrame,
    output_dir: str | Path,
) -> Path:
    """Create an interactive great-circle route map between two airports.

    Parameters
    ----------
    origin, destination:
        IATA airport codes (e.g. ``"JFK"``, ``"LAX"``).
    airports:
        DataFrame with columns ``iata_code``, ``latitude_deg``, ``longitude_deg``,
        and optionally ``name``. Compatible with the OurAirports airports.csv format.
    output_dir:
        Directory where the HTML file will be written.

    Returns
    -------
    Path to the saved HTML file.
    """
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    orig = _lookup_airport(airports, origin)
    dest = _lookup_airport(airports, destination)

    fig = go.Figure()

    fig.add_trace(
        go.Scattergeo(
            lon=[orig["lon"], dest["lon"]],
            lat=[orig["lat"], dest["lat"]],
            mode="lines",
            line={"width": 2, "color": "#2563eb"},
            name=f"{origin} → {destination}",
        )
    )

    fig.add_trace(
        go.Scattergeo(
            lon=[orig["lon"], dest["lon"]],
            lat=[orig["lat"], dest["lat"]],
            mode="markers+text",
            marker={"size": 10, "color": "#dc2626"},
            text=[orig["name"], dest["name"]],
            textposition="top center",
            name="Airports",
        )
    )

    fig.update_layout(
        title=f"Flight Path: {origin} → {destination}",
        geo={
            "projection_type": "natural earth",
            "showland": True,
            "landcolor": "#e5e7eb",
            "showocean": True,
            "oceancolor": "#dbeafe",
            "showcountries": True,
            "countrycolor": "#9ca3af",
            "showcoastlines": True,
        },
        margin={"l": 0, "r": 0, "t": 40, "b": 0},
    )

    out_path = output / f"flight_path_{origin}_{destination}.html"
    fig.write_html(out_path, include_plotlyjs="cdn")
    return out_path


def plot_live_flights(
    origin: str,
    destination: str,
    airports: pd.DataFrame,
    output_dir: str | Path,
) -> Path:
    """Fetch live aircraft positions from OpenSky Network and overlay on the route.

    Uses the OpenSky Network public REST API (no authentication required for basic
    state vectors, but rate-limited). Degrades gracefully when the API is unavailable.

    Parameters
    ----------
    origin, destination:
        IATA airport codes used to label endpoints and build the bounding box.
    airports:
        Airport lookup DataFrame (OurAirports format).
    output_dir:
        Directory where the HTML file will be written.

    Returns
    -------
    Path to the saved HTML file.
    """
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    orig = _lookup_airport(airports, origin)
    dest = _lookup_airport(airports, destination)

    lat_min = min(orig["lat"], dest["lat"]) - 5
    lat_max = max(orig["lat"], dest["lat"]) + 5
    lon_min = min(orig["lon"], dest["lon"]) - 5
    lon_max = max(orig["lon"], dest["lon"]) + 5

    url = (
        "https://opensky-network.org/api/states/all"
        f"?lamin={lat_min:.2f}&lamax={lat_max:.2f}"
        f"&lomin={lon_min:.2f}&lomax={lon_max:.2f}"
    )

    live_lats: list[float] = []
    live_lons: list[float] = []
    live_labels: list[str] = []
    try:
        with urlopen(url, timeout=10) as resp:  # noqa: S310
            data = json.loads(resp.read())
        for state in data.get("states") or []:
            lon, lat = state[5], state[6]
            if lon is not None and lat is not None:
                live_lons.append(float(lon))
                live_lats.append(float(lat))
                live_labels.append((state[1] or "").strip() or "unknown")
    except (URLError, Exception):
        pass

    fig = go.Figure()

    fig.add_trace(
        go.Scattergeo(
            lon=[orig["lon"], dest["lon"]],
            lat=[orig["lat"], dest["lat"]],
            mode="lines",
            line={"width": 2, "color": "#2563eb", "dash": "dash"},
            name=f"{origin} → {destination} route",
        )
    )

    fig.add_trace(
        go.Scattergeo(
            lon=[orig["lon"], dest["lon"]],
            lat=[orig["lat"], dest["lat"]],
            mode="markers+text",
            marker={"size": 12, "color": "#dc2626", "symbol": "star"},
            text=[orig["name"], dest["name"]],
            textposition="top center",
            name="Airports",
        )
    )

    if live_lats:
        fig.add_trace(
            go.Scattergeo(
                lon=live_lons,
                lat=live_lats,
                mode="markers",
                marker={"size": 6, "color": "#f59e0b", "symbol": "triangle-up"},
                text=live_labels,
                hovertemplate="%{text}<extra></extra>",
                name="Live aircraft",
            )
        )

    fig.update_layout(
        title=f"Live Flights Near Route: {origin} → {destination}",
        geo={
            "projection_type": "natural earth",
            "showland": True,
            "landcolor": "#e5e7eb",
            "showocean": True,
            "oceancolor": "#dbeafe",
            "showcountries": True,
            "countrycolor": "#9ca3af",
            "showcoastlines": True,
            "lataxis": {"range": [lat_min, lat_max]},
            "lonaxis": {"range": [lon_min, lon_max]},
        },
        margin={"l": 0, "r": 0, "t": 40, "b": 0},
    )

    out_path = output / f"live_flights_{origin}_{destination}.html"
    fig.write_html(out_path, include_plotlyjs="cdn")
    return out_path


def create_visualizations(ranked_options: pd.DataFrame, output_dir: str | Path) -> dict[str, Path]:
    """Create Plotly HTML visualizations and return their file paths."""
    if ranked_options.empty:
        raise ValueError("Cannot create visualizations for an empty ranking table.")

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    value_chart = output / "value_score_by_airline.html"
    reliability_chart = output / "on_time_rate_by_airline.html"
    tradeoff_chart = output / "duration_delay_tradeoff.html"

    value_fig = px.bar(
        ranked_options,
        x="airline",
        y="value_score",
        title="Lower Value Score Is Better",
        labels={"airline": "Airline", "value_score": "Value score"},
    )
    value_fig.write_html(value_chart, include_plotlyjs="cdn")

    reliability_fig = px.bar(
        ranked_options,
        x="airline",
        y="on_time_rate",
        title="Historical On-Time Rate by Airline",
        labels={"airline": "Airline", "on_time_rate": "On-time rate"},
    )
    reliability_fig.write_html(reliability_chart, include_plotlyjs="cdn")

    tradeoff_fig = px.scatter(
        ranked_options,
        x="avg_duration_min",
        y="avg_positive_arr_delay_min",
        size="sample_size",
        hover_name="airline",
        title="Duration vs Delay Trade-off",
        labels={
            "avg_duration_min": "Average duration (min)",
            "avg_positive_arr_delay_min": "Average positive arrival delay (min)",
            "sample_size": "Sample size",
        },
    )
    tradeoff_fig.write_html(tradeoff_chart, include_plotlyjs="cdn")

    return {
        "value_score": value_chart,
        "on_time_rate": reliability_chart,
        "duration_delay_tradeoff": tradeoff_chart,
    }
