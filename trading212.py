import os
from functools import lru_cache

import pandas as pd
import requests
from dotenv import load_dotenv


load_dotenv()

API_KEY = os.getenv("TRADING212_API_KEY")
API_SECRET = os.getenv("TRADING212_API_SECRET")
BASE_URL = os.getenv("TRADING212_BASE_URL")


def _check_credentials():
    if not API_KEY or not API_SECRET or not BASE_URL:
        raise RuntimeError(
            "Trading 212 credentials are missing. Check your .env file."
        )


def _get(endpoint):
    _check_credentials()

    response = requests.get(
        f"{BASE_URL}{endpoint}",
        auth=(API_KEY, API_SECRET),
        timeout=20,
    )

    response.raise_for_status()

    return response.json()


def get_account_summary():
    return _get("/equity/account/summary")


@lru_cache(maxsize=1)
def get_instrument_metadata():
    instruments = _get("/equity/metadata/instruments")

    return {
        instrument["ticker"]: instrument
        for instrument in instruments
        if instrument.get("ticker")
    }


def _fallback_ticker(ticker):
    if ticker.endswith("_US_EQ"):
        return ticker.removesuffix("_US_EQ")

    if ticker.endswith("_EQ"):
        return ticker.removesuffix("_EQ")

    return ticker


def get_positions():
    positions = _get("/equity/positions")

    try:
        metadata = get_instrument_metadata()
    except requests.RequestException:
        metadata = {}

    cleaned_positions = []

    for position in positions:
        instrument = position["instrument"]
        wallet = position["walletImpact"]

        internal_ticker = instrument["ticker"]

        instrument_metadata = metadata.get(
            internal_ticker,
            {},
        )

        display_ticker = (
            instrument_metadata.get("shortName")
            or _fallback_ticker(internal_ticker)
        )

        company = (
            instrument_metadata.get("name")
            or instrument.get("name")
            or display_ticker
        )

        instrument_currency = (
            instrument_metadata.get("currencyCode")
            or instrument.get("currency")
        )

        cleaned_positions.append(
            {
                "ticker": internal_ticker,
                "display_ticker": display_ticker,
                "company": company,
                "isin": instrument.get("isin"),
                "instrument_currency": instrument_currency,
                "instrument_type": instrument_metadata.get("type"),
                "quantity": position["quantity"],
                "average_price": position["averagePricePaid"],
                "current_price": position["currentPrice"],
                "total_cost": wallet["totalCost"],
                "current_value": wallet["currentValue"],
                "unrealised_pnl": wallet["unrealizedProfitLoss"],
                "fx_impact": wallet.get("fxImpact", 0),
                "account_currency": wallet["currency"],
            }
        )

    return pd.DataFrame(cleaned_positions)