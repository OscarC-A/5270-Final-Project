"""Convenience runner that calls the package CLI.

Example:
    python scripts/run_analysis.py --input data/raw/bts_flights.csv --origin JFK --destination LAX
"""

from flight_value_checker.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
