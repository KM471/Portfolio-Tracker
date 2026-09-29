import os
import time
from functools import lru_cache
from urllib.parse import urljoin

import pandas as pd
import requests
import streamlit as st
from dotenv import load_dotenv


# ============================================================
# Credentials
# ============================================================

# Local computer:
# Loads credentials from the .env file.
#
# Streamlit Cloud:
# Loads credentials from Streamlit Secrets.
#
# The actual credential values are never stored in the code.

load_dotenv()


def _get_setting(name):
    # First try normal environment variables.
    # Locally these are populated by load_dotenv().
    value = os.getenv(name)

    if value:
        return str(value).strip()

    # If not found, try Streamlit Cloud Secrets.
    try:
        value = st.secrets[name]

        if value:
            return str(value).strip()

    except (KeyError, FileNotFoundError):
        pass

    except Exception:
        pass

    return None


API_KEY = _get_setting(
    "TRADING212_API_KEY"
)

API_SECRET = _get_setting(
    "TRADING212_API_SECRET"
)

BASE_URL = _get_setting(
    "TRADING212_BASE_URL"
)


def _check_credentials():
    missing = []

    if not API_KEY:
        missing.append(
            "TRADING212_API_KEY"
        )

    if not API_SECRET:
        missing.append(
            "TRADING212_API_SECRET"
        )

    if not BASE_URL:
        missing.append(
            "TRADING212_BASE_URL"
        )

    if missing:
        try:
            available_secret_names = list(
                st.secrets.keys()
            )
        except Exception:
            available_secret_names = []

        raise RuntimeError(
            "Trading 212 credentials are missing. "
            f"Missing: {', '.join(missing)}. "
            "Streamlit secret names currently visible to the app: "
            f"{available_secret_names}"
        )


# ============================================================
# HTTP helpers
# ============================================================

def _request_url(url, params=None):
    _check_credentials()

    response = requests.get(
        url,
        auth=(API_KEY, API_SECRET),
        params=params,
        timeout=30,
    )

    if response.status_code == 429:
        print(
            "Trading 212 rate limit reached. "
            "Waiting 12 seconds..."
        )

        time.sleep(12)

        response = requests.get(
            url,
            auth=(API_KEY, API_SECRET),
            params=params,
            timeout=30,
        )

    response.raise_for_status()

    return response.json()


def _get(endpoint, params=None):
    return _request_url(
        f"{BASE_URL}{endpoint}",
        params=params,
    )


def _get_all_pages(endpoint):
    data = _get(
        endpoint,
        params={"limit": 50},
    )

    all_items = data.get(
        "items",
        [],
    )

    next_page = data.get(
        "nextPagePath"
    )

    while next_page:
        next_url = urljoin(
            BASE_URL + "/",
            next_page,
        )

        data = _request_url(
            next_url
        )

        all_items.extend(
            data.get(
                "items",
                [],
            )
        )

        next_page = data.get(
            "nextPagePath"
        )

    return all_items


# ============================================================
# Tax handling
# ============================================================

def _normalise_taxes(
    taxes,
    wallet_currency,
):
    if taxes is None:
        return 0.0, 0

    if isinstance(
        taxes,
        (int, float),
    ):
        return float(taxes), 0

    if not isinstance(
        taxes,
        list,
    ):
        return 0.0, 0

    total = 0.0
    unconverted_count = 0

    for tax in taxes:
        if not isinstance(
            tax,
            dict,
        ):
            continue

        quantity = tax.get(
            "quantity"
        )

        tax_currency = tax.get(
            "currency"
        )

        if quantity is None:
            continue

        try:
            quantity = float(
                quantity
            )

        except (
            TypeError,
            ValueError,
        ):
            continue

        if (
            not tax_currency
            or not wallet_currency
            or tax_currency
            == wallet_currency
        ):
            total += quantity

        else:
            unconverted_count += 1

    return (
        total,
        unconverted_count,
    )


# ============================================================
# Account
# ============================================================

def get_account_summary():
    return _get(
        "/equity/account/summary"
    )


# ============================================================
# Instrument metadata
# ============================================================

@lru_cache(maxsize=1)
def get_instrument_metadata():
    instruments = _get(
        "/equity/metadata/instruments"
    )

    return {
        instrument["ticker"]: instrument
        for instrument in instruments
        if instrument.get("ticker")
    }


def _fallback_ticker(
    ticker,
):
    if ticker.endswith(
        "_US_EQ"
    ):
        return ticker.removesuffix(
            "_US_EQ"
        )

    if ticker.endswith(
        "_EQ"
    ):
        return ticker.removesuffix(
            "_EQ"
        )

    return ticker


# ============================================================
# Positions
# ============================================================

def get_positions():
    positions = _get(
        "/equity/positions"
    )

    try:
        metadata = (
            get_instrument_metadata()
        )

    except requests.RequestException:
        metadata = {}

    cleaned_positions = []

    for position in positions:
        instrument = position[
            "instrument"
        ]

        wallet = position[
            "walletImpact"
        ]

        internal_ticker = instrument[
            "ticker"
        ]

        instrument_metadata = (
            metadata.get(
                internal_ticker,
                {},
            )
        )

        display_ticker = (
            instrument_metadata.get(
                "shortName"
            )
            or _fallback_ticker(
                internal_ticker
            )
        )

        company = (
            instrument_metadata.get(
                "name"
            )
            or instrument.get(
                "name"
            )
            or display_ticker
        )

        instrument_currency = (
            instrument_metadata.get(
                "currencyCode"
            )
            or instrument.get(
                "currency"
            )
        )

        cleaned_positions.append(
            {
                "ticker": internal_ticker,
                "display_ticker": (
                    display_ticker
                ),
                "company": company,
                "isin": instrument.get(
                    "isin"
                ),
                "instrument_currency": (
                    instrument_currency
                ),
                "instrument_type": (
                    instrument_metadata.get(
                        "type"
                    )
                ),
                "quantity": position[
                    "quantity"
                ],
                "average_price": position[
                    "averagePricePaid"
                ],
                "current_price": position[
                    "currentPrice"
                ],
                "total_cost": wallet[
                    "totalCost"
                ],
                "current_value": wallet[
                    "currentValue"
                ],
                "unrealised_pnl": wallet[
                    "unrealizedProfitLoss"
                ],
                "fx_impact": wallet.get(
                    "fxImpact",
                    0,
                ),
                "account_currency": wallet[
                    "currency"
                ],
            }
        )

    return pd.DataFrame(
        cleaned_positions
    )


# ============================================================
# Transactions
# ============================================================

def get_all_transactions():
    transactions = (
        _get_all_pages(
            "/equity/history/transactions"
        )
    )

    return pd.DataFrame(
        transactions
    )


# ============================================================
# Dividends
# ============================================================

def get_all_dividends():
    dividends = _get_all_pages(
        "/equity/history/dividends"
    )

    return pd.DataFrame(
        dividends
    )


# ============================================================
# Orders
# ============================================================

def get_all_orders():
    items = _get_all_pages(
        "/equity/history/orders"
    )

    cleaned_orders = []

    for item in items:
        order = (
            item.get("order")
            or {}
        )

        fill = (
            item.get("fill")
            or {}
        )

        instrument = (
            order.get("instrument")
            or {}
        )

        wallet = (
            fill.get("walletImpact")
            or {}
        )

        wallet_currency = (
            wallet.get("currency")
        )

        (
            tax_total,
            unconverted_tax_count,
        ) = _normalise_taxes(
            wallet.get("taxes"),
            wallet_currency,
        )

        cleaned_orders.append(
            {
                "order_id": order.get(
                    "id"
                ),
                "ticker": order.get(
                    "ticker"
                ),
                "side": order.get(
                    "side"
                ),
                "order_type": order.get(
                    "type"
                ),
                "status": order.get(
                    "status"
                ),
                "created_at": order.get(
                    "createdAt"
                ),
                "filled_at": fill.get(
                    "filledAt"
                ),
                "quantity": fill.get(
                    "quantity"
                ),
                "price": fill.get(
                    "price"
                ),
                "currency": order.get(
                    "currency"
                ),
                "order_value": order.get(
                    "value"
                ),
                "filled_value": order.get(
                    "filledValue"
                ),
                "instrument_name": (
                    instrument.get(
                        "name"
                    )
                ),
                "net_value": wallet.get(
                    "netValue",
                    0,
                ),
                "realised_pnl": (
                    wallet.get(
                        "realisedProfitLoss",
                        0,
                    )
                ),
                "taxes": tax_total,
                "unconverted_tax_count": (
                    unconverted_tax_count
                ),
                "fx_rate": wallet.get(
                    "fxRate"
                ),
                "wallet_currency": (
                    wallet_currency
                ),
            }
        )

    return pd.DataFrame(
        cleaned_orders
    )