"""Interactive route search.

Prompts:
    1. Origin airport (IATA, e.g. JFK)
    2. Destination airport (IATA, e.g. LAX)
    3. Do you want connections? (Y/N)
    4. If Y: number of connections (1 or 2)

Run from the repo root:
    python scripts/custom_test.py
"""

from __future__ import annotations

import sys
import webbrowser
from pathlib import Path

# Windows console defaults to cp1252 — switch to UTF-8 so the arrow glyph prints.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from flight_value_checker.clean import clean_flight_data
from flight_value_checker.ingest import load_airports, load_flight_data
from flight_value_checker.rank import find_connecting_routes
from flight_value_checker.visualize import plot_route_options

DEFAULT_INPUT = Path("data/raw/bts_flights.csv")
DEFAULT_ASSETS = Path("docs/assets")


def prompt_airport(label: str) -> str:
    while True:
        value = input(f"{label} (IATA code, 3 letters): ").strip().upper()
        if len(value) == 3 and value.isalpha():
            return value
        print("  Please enter a 3-letter IATA code (e.g. JFK).")


def prompt_yes_no(label: str) -> bool:
    while True:
        value = input(f"{label} [Y/N]: ").strip().upper()
        if value in ("Y", "YES"):
            return True
        if value in ("N", "NO"):
            return False
        print("  Please answer Y or N.")


def prompt_int(label: str, minimum: int, maximum: int, default: int) -> int:
    while True:
        raw = input(f"{label} ({minimum}-{maximum}, default {default}): ").strip()
        if not raw:
            return default
        try:
            value = int(raw)
        except ValueError:
            print(f"  Please enter a whole number between {minimum} and {maximum}.")
            continue
        if minimum <= value <= maximum:
            return value
        print(f"  Please enter a whole number between {minimum} and {maximum}.")


def main() -> int:
    print()
    print("=" * 60)
    print("  Flight Value Checker — Custom Route Test")
    print("=" * 60)

    origin = prompt_airport("Origin airport")
    destination = prompt_airport("Destination airport")
    if origin == destination:
        print("Origin and destination must differ.", file=sys.stderr)
        return 1

    include_connections = prompt_yes_no("Do you want connections?")
    max_stops = 0
    if include_connections:
        max_stops = prompt_int("Number of connections", minimum=1, maximum=2, default=1)

    if not DEFAULT_INPUT.exists():
        print(f"\nMissing dataset: {DEFAULT_INPUT}")
        print("Download BTS data first; see README.")
        return 1

    print(f"\nLoading {DEFAULT_INPUT} ...")
    raw = load_flight_data(DEFAULT_INPUT)
    print(f"Cleaning {len(raw):,} rows ...")
    cleaned = clean_flight_data(raw)

    descriptor = "direct" if max_stops == 0 else f"up to {max_stops} stop{'s' if max_stops > 1 else ''}"
    print(f"Searching for routes {origin} → {destination} ({descriptor}) ...")

    routes = find_connecting_routes(
        cleaned, origin=origin, destination=destination, max_stops=max_stops, top_n=15
    )
    if routes.empty:
        print(f"\nNo routes found for {origin} → {destination} within {max_stops} stop(s).")
        return 1

    direct_count = int((routes["n_stops"] == 0).sum())
    one_stop_count = int((routes["n_stops"] == 1).sum())
    two_stop_count = int((routes["n_stops"] == 2).sum())
    print(
        f"\nFound {len(routes)} option(s): "
        f"{direct_count} direct, {one_stop_count} one-stop, {two_stop_count} two-stop."
    )

    display_cols = [
        "path_label",
        "n_stops",
        "total_duration_min",
        "on_time_rate",
        "value_score",
        "sample_size",
    ]
    print()
    print(routes[display_cols].to_string(index=False, float_format="{:.2f}".format))

    print("\nBuilding map ...")
    airports = load_airports()
    map_path = plot_route_options(
        routes, airports, DEFAULT_ASSETS, origin, destination, top_n=10
    )
    print(f"\nMap written to: {map_path}")

    if prompt_yes_no("Open the map in your browser?"):
        webbrowser.open(map_path.resolve().as_uri())

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nCancelled.", file=sys.stderr)
        raise SystemExit(130)
