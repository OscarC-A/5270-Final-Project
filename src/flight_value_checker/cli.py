"""Command-line entry point for the flight value checker."""

from __future__ import annotations

import argparse
from pathlib import Path

from flight_value_checker.clean import clean_flight_data
from flight_value_checker.ingest import load_airports, load_flight_data, save_processed_data
from flight_value_checker.rank import rank_carrier_options
from flight_value_checker.report import build_html_report
from flight_value_checker.visualize import create_visualizations, plot_flight_path, plot_live_flights


def build_parser() -> argparse.ArgumentParser:
    """Create the command-line parser."""
    parser = argparse.ArgumentParser(description="Rank flight route options using historical data.")
    parser.add_argument("--input", required=True, help="Path to a raw CSV or Parquet flight dataset.")
    parser.add_argument("--origin", required=True, help="Origin airport code, e.g. JFK.")
    parser.add_argument("--destination", required=True, help="Destination airport code, e.g. LAX.")
    parser.add_argument("--top-n", type=int, default=10, help="Number of ranked options to show.")
    parser.add_argument("--processed-output", default="data/processed/clean_flights.csv")
    parser.add_argument("--report-output", default="docs/report.html")
    parser.add_argument("--assets-dir", default="docs/assets")
    parser.add_argument(
        "--airports",
        default=None,
        help="Path to OurAirports airports.csv. Downloaded automatically if omitted.",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Overlay live aircraft positions from OpenSky Network on the route map.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the full pipeline from raw data to HTML report."""
    args = build_parser().parse_args(argv)

    raw = load_flight_data(args.input)
    cleaned = clean_flight_data(raw)
    save_processed_data(cleaned, args.processed_output)

    ranked = rank_carrier_options(
        cleaned,
        origin=args.origin,
        destination=args.destination,
        top_n=args.top_n,
    )
    if ranked.empty:
        raise SystemExit(f"No flights found for {args.origin.upper()} -> {args.destination.upper()}.")

    chart_files = create_visualizations(ranked, args.assets_dir)

    airports_df = load_airports(args.airports)
    chart_files["flight_path"] = plot_flight_path(
        args.origin, args.destination, airports_df, args.assets_dir
    )
    if args.live:
        chart_files["live_flights"] = plot_live_flights(
            args.origin, args.destination, airports_df, args.assets_dir
        )

    report_path = build_html_report(
        ranked,
        chart_files,
        Path(args.report_output),
        title=f"Flight Value Checker: {args.origin.upper()} to {args.destination.upper()}",
    )
    print(f"Report written to {report_path}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
