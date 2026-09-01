import os

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
        timeout=15,
    )

    response.raise_for_status()

    return response.json()


def get_account_summary():
    return _get("/equity/account/summary")


def get_positions():
    positions = _get("/equity/positions")

    cleaned_positions = []

    for position in positions:
        instrument = position["instrument"]
        wallet = position["walletImpact"]

        cleaned_positions.append(
            {
                "ticker": instrument["ticker"],
                "company": instrument["name"],
                "isin": instrument["isin"],
                "instrument_currency": instrument["currency"],
                "quantity": position["quantity"],
                "average_price": position["averagePricePaid"],
                "current_price": position["currentPrice"],
                "total_cost": wallet["totalCost"],
                "current_value": wallet["currentValue"],
                "unrealised_pnl": wallet["unrealizedProfitLoss"],
                "fx_impact": wallet["fxImpact"],
                "account_currency": wallet["currency"],
            }
        )

    return pd.DataFrame(cleaned_positions)