"""Safe static-HTML parsing example.

This module is intentionally scoped to local or permitted static HTML. It should not be
used to scrape Google Flights, Expedia, or other protected/dynamic sites without checking
and following their terms of service.
"""

from __future__ import annotations

import pandas as pd
from bs4 import BeautifulSoup


def parse_static_flight_cards(html: str) -> pd.DataFrame:
    """Parse simple flight cards from static HTML into a DataFrame.

    Expected card format:
        <div class="flight-card" data-origin="JFK" data-destination="LAX"
             data-airline="DL" data-duration-min="370" data-price-usd="250"></div>
    """
    soup = BeautifulSoup(html, "html.parser")
    records = []
    for card in soup.select(".flight-card"):
        record = {
            "origin": card.get("data-origin"),
            "destination": card.get("data-destination"),
            "airline": card.get("data-airline"),
            "duration_min": card.get("data-duration-min"),
            "price_usd": card.get("data-price-usd"),
            "arr_delay_min": card.get("data-arr-delay-min", 0),
        }
        if all(record[key] is not None for key in ["origin", "destination", "airline", "duration_min"]):
            records.append(record)

    return pd.DataFrame.from_records(records)
