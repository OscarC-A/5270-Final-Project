"""HTML report builder for the flight value checker."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def _relative_link(target: Path, base: Path) -> str:
    """Return a portable relative link from an HTML report to an asset."""
    try:
        return target.resolve().relative_to(base.resolve().parent).as_posix()
    except ValueError:
        return target.as_posix()


def build_html_report(
    ranked_options: pd.DataFrame,
    chart_files: dict[str, Path] | None,
    output_path: str | Path,
    title: str = "Flight Value Checker Report",
    source_note: str = "Source: BTS On-Time Performance data or user-provided flight dataset.",
) -> Path:
    """Build a lightweight HTML report with rankings and chart links."""
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    table_html = ranked_options.to_html(index=False, classes="ranking-table", float_format="{:.3f}".format)
    chart_files = chart_files or {}
    chart_items = "\n".join(
        f'<li><a href="{_relative_link(Path(path), output)}">{name.replace("_", " ").title()}</a></li>'
        for name, path in chart_files.items()
    )
    if not chart_items:
        chart_items = "<li>No chart files were generated.</li>"

    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{title}</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 2rem; line-height: 1.45; }}
    h1, h2 {{ color: #1f2937; }}
    .note {{ color: #4b5563; }}
    .ranking-table {{ border-collapse: collapse; width: 100%; margin-top: 1rem; }}
    .ranking-table th, .ranking-table td {{ border: 1px solid #d1d5db; padding: 0.45rem; }}
    .ranking-table th {{ background: #f3f4f6; }}
  </style>
</head>
<body>
  <h1>{title}</h1>
  <p class="note">{source_note}</p>
  <h2>Ranked Route Options</h2>
  {table_html}
  <h2>Visualizations</h2>
  <ul>
    {chart_items}
  </ul>
  <h2>Interpretation Guide</h2>
  <p>Lower value score is better. The score balances historical arrival delay, duration, and price when price data is available.</p>
</body>
</html>
"""
    output.write_text(html, encoding="utf-8")
    return output
