from pathlib import Path

from flight_value_checker.cli import build_parser, main

FIXTURE = Path(__file__).parent / "fixtures" / "sample_flights.csv"


def test_build_parser_has_expected_description():
    parser = build_parser()
    assert "Rank flight route options" in parser.description


def test_cli_main_runs_pipeline(tmp_path):
    processed = tmp_path / "clean.csv"
    report = tmp_path / "report.html"
    assets = tmp_path / "assets"

    exit_code = main(
        [
            "--input",
            str(FIXTURE),
            "--origin",
            "JFK",
            "--destination",
            "LAX",
            "--processed-output",
            str(processed),
            "--report-output",
            str(report),
            "--assets-dir",
            str(assets),
        ]
    )

    assert exit_code == 0
    assert processed.exists()
    assert report.exists()
    assert (assets / "value_score_by_airline.html").exists()
