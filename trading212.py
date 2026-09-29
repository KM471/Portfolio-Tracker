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

# Local development:
#   Reads credentials from .env
#
# Streamlit Cloud:
#   Reads credentials from Streamlit Secrets
#
# .env remains excluded from Git and is never uploaded.

load_dotenv()


def _get_setting(name, default=None):
    """
    Get a configuration value.

    Priority:
    1. Environment variable / local .env
    2. Streamlit Secrets
    3. Supplied default
    """

    value = os.getenv(name)

    if value is not None and str(value).strip():
        return str(value).strip()

    try:
        if name in st.secrets:
            value = st.secrets[name]

            if value is not None and str(value).strip():
                return str(value).strip()

    except Exception:
        # This is normal when running locally without
        # .streamlit/secrets.toml.
        pass

    return default


API_KEY = _get_setting("TRADING212_API_KEY")
API_SECRET = _get_setting("TRADING212_API_SECRET")

BASE_URL = _get_setting(
    "TRADING212_BASE_URL",
    "https://live.trading212.com/api/v0",
).rstrip("/")


def _check_credentials():
    if not API_KEY or not API_SECRET:
        raise ValueError(
            "Trading 212 credentials are missing. "
            "Add TRADING212_API_KEY and TRADING212_API_SECRET "
            "to your local .env file or Streamlit Secrets."
        )


# ============================================================
# HTTP helpers
# ============================================================

def _request_url(url, params=None):
    """
    Send an authenticated GET request to Trading 212.
    """

    _check_credentials()

    response = requests.get(
        url,
        auth=(API_KEY, API_SECRET),
        params=params,
        timeout=30,
    )

    # Simple retry for Trading 212 rate limiting.
    if response.status_code == 429:
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
    """
    Request an endpoint relative to the Trading 212 base URL.
    """

    url = f"{BASE_URL}{endpoint}"

    return _request_url(
        url,
        params=params,
    )


def _get_all_pages(endpoint):
    """
    Retrieve every page from a paginated Trading 212 endpoint.
    """

    payload = _get(
        endpoint,
        params={"limit": 50},
    )

    # Some Trading 212 endpoints may return a plain list.
    if isinstance(payload, list):
        return payload

    items = list(
        payload.get("items", [])
    )

    next_page = payload.get(
        "nextPagePath"
    )

    seen_pages = set()

    while next_page:

        # Prevent an accidental infinite pagination loop.
        if next_page in seen_pages:
            break

        seen_pages.add(next_page)

        next_url = urljoin(
            BASE_URL + "/",
            next_page,
        )

        payload = _request_url(
            next_url
        )

        if isinstance(payload, list):
            items.extend(payload)
            break

        items.extend(
            payload.get("items", [])
        )

        next_page = payload.get(
            "nextPagePath"
        )

    return items


# ============================================================
# Account
# ============================================================

def get_account_summary():
    """
    Return the live Trading 212 account summary.
    """

    return _get(
        "/equity/account/summary"
    )


# ============================================================
# Instrument metadata
# ============================================================

@lru_cache(maxsize=1)
def get_instrument_metadata():
    """
    Return Trading 212 instrument metadata indexed by
    internal Trading 212 ticker.
    """

    try:
        data = _get(
            "/equity/metadata/instruments"
        )

    except Exception:
        # Metadata improves display names but is not required
        # for the rest of the portfolio calculations.
        return {}

    if isinstance(data, dict):
        instruments = data.get(
            "items",
            [],
        )
    else:
        instruments = data

    metadata = {}

    for instrument in instruments:

        ticker = instrument.get(
            "ticker"
        )

        if ticker:
            metadata[ticker] = instrument

    return metadata


def _fallback_ticker(ticker):
    """
    Convert Trading 212 internal ticker names into a cleaner
    fallback display value when metadata is unavailable.
    """

    if not ticker:
        return ""

    if ticker.endswith("_US_EQ"):
        return ticker[:-6]

    if ticker.endswith("_EQ"):
        return ticker[:-3]

    return ticker


# ============================================================
# Current positions
# ============================================================

def get_positions():
    """
    Return current open positions as a cleaned DataFrame.
    """

    positions = _get(
        "/equity/positions"
    )

    metadata = get_instrument_metadata()

    rows = []

    for position in positions:

        instrument = position.get(
            "instrument",
            {},
        )

        internal_ticker = instrument.get(
            "ticker",
            "",
        )

        instrument_metadata = metadata.get(
            internal_ticker,
            {},
        )

        wallet_impact = position.get(
            "walletImpact",
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

        rows.append(
            {
                "ticker": internal_ticker,
                "display_ticker": display_ticker,
                "company": company,
                "isin": (
                    instrument_metadata.get("isin")
                    or instrument.get("isin")
                ),
                "instrument_currency": instrument_currency,
                "instrument_type": instrument_metadata.get(
                    "type"
                ),
                "quantity": position.get(
                    "quantity"
                ),
                "average_price": position.get(
                    "averagePricePaid"
                ),
                "current_price": position.get(
                    "currentPrice"
                ),
                "total_cost": wallet_impact.get(
                    "totalCost"
                ),
                "current_value": wallet_impact.get(
                    "currentValue"
                ),
                "unrealised_pnl": wallet_impact.get(
                    "unrealizedProfitLoss"
                ),
                "fx_impact": wallet_impact.get(
                    "fxImpact"
                ),
                "account_currency": wallet_impact.get(
                    "currency"
                ),
            }
        )

    columns = [
        "ticker",
        "display_ticker",
        "company",
        "isin",
        "instrument_currency",
        "instrument_type",
        "quantity",
        "average_price",
        "current_price",
        "total_cost",
        "current_value",
        "unrealised_pnl",
        "fx_impact",
        "account_currency",
    ]

    return pd.DataFrame(
        rows,
        columns=columns,
    )


# ============================================================
# Transactions
# ============================================================

def get_all_transactions():
    """
    Return complete Trading 212 transaction history.
    """

    items = _get_all_pages(
        "/equity/history/transactions"
    )

    return pd.DataFrame(items)


# ============================================================
# Dividends
# ============================================================

def get_all_dividends():
    """
    Return complete Trading 212 dividend history.
    """

    items = _get_all_pages(
        "/equity/history/dividends"
    )

    return pd.DataFrame(items)


# ============================================================
# Historical orders
# ============================================================

def _safe_float(value):
    """
    Convert a value to float when possible.
    """

    if value is None:
        return None

    try:
        return float(value)

    except (TypeError, ValueError):
        return None


def _normalise_taxes(
    taxes,
    wallet_currency=None,
):
    """
    Convert Trading 212 tax information into a numeric amount
    where possible.

    Returns:
        tax_total,
        unconverted_tax_count
    """

    if taxes is None:
        return 0.0, 0

    if isinstance(
        taxes,
        (int, float),
    ):
        return float(taxes), 0

    if isinstance(taxes, dict):
        taxes = [taxes]

    total = 0.0
    unconverted_count = 0

    for tax in taxes:

        if not isinstance(tax, dict):
            value = _safe_float(tax)

            if value is None:
                unconverted_count += 1
            else:
                total += value

            continue

        quantity = _safe_float(
            tax.get("quantity")
        )

        tax_currency = tax.get(
            "currency"
        )

        if quantity is None:
            unconverted_count += 1
            continue

        # If the tax is already in the wallet currency,
        # it can be included directly.
        if (
            not tax_currency
            or not wallet_currency
            or tax_currency == wallet_currency
        ):
            total += quantity
        else:
            # Keep track of taxes which would require
            # an FX conversion instead of silently
            # treating them as the wallet currency.
            unconverted_count += 1

    return total, unconverted_count


def get_all_orders():
    """
    Return complete historical order history as a cleaned
    DataFrame used by the portfolio reconstruction code.
    """

    items = _get_all_pages(
        "/equity/history/orders"
    )

    rows = []

    for item in items:

        order = item.get(
            "order",
            {},
        ) or {}

        fill = item.get(
            "fill",
            {},
        ) or {}

        instrument = order.get(
            "instrument",
            {},
        ) or {}

        wallet_impact = fill.get(
            "walletImpact",
            {},
        ) or {}

        wallet_currency = wallet_impact.get(
            "currency"
        )

        taxes, unconverted_tax_count = (
            _normalise_taxes(
                wallet_impact.get("taxes"),
                wallet_currency,
            )
        )

        order_quantity = _safe_float(
            order.get("quantity")
        )

        filled_quantity = _safe_float(
            fill.get("quantity")
        )

        if filled_quantity is None:
            filled_quantity = _safe_float(
                order.get("filledQuantity")
            )

        if filled_quantity is None:
            filled_quantity = order_quantity

        price = _safe_float(
            fill.get("price")
        )

        order_value = None
        filled_value = None

        if (
            order_quantity is not None
            and price is not None
        ):
            order_value = abs(
                order_quantity * price
            )

        if (
            filled_quantity is not None
            and price is not None
        ):
            filled_value = abs(
                filled_quantity * price
            )

        rows.append(
            {
                "order_id": order.get("id"),
                "ticker": (
                    order.get("ticker")
                    or instrument.get("ticker")
                ),
                "side": order.get("side"),
                "order_type": order.get("type"),
                "status": order.get("status"),
                "created_at": order.get(
                    "createdAt"
                ),
                "filled_at": fill.get(
                    "filledAt"
                ),
                "quantity": filled_quantity,
                "price": price,
                "currency": instrument.get(
                    "currency"
                ),
                "order_value": order_value,
                "filled_value": filled_value,
                "instrument_name": instrument.get(
                    "name"
                ),
                "net_value": wallet_impact.get(
                    "netValue"
                ),
                "realised_pnl": wallet_impact.get(
                    "realisedProfitLoss"
                ),
                "taxes": taxes,
                "unconverted_tax_count": (
                    unconverted_tax_count
                ),
                "fx_rate": wallet_impact.get(
                    "fxRate"
                ),
                "wallet_currency": (
                    wallet_currency
                ),
            }
        )

    columns = [
        "order_id",
        "ticker",
        "side",
        "order_type",
        "status",
        "created_at",
        "filled_at",
        "quantity",
        "price",
        "currency",
        "order_value",
        "filled_value",
        "instrument_name",
        "net_value",
        "realised_pnl",
        "taxes",
        "unconverted_tax_count",
        "fx_rate",
        "wallet_currency",
    ]

    return pd.DataFrame(
        rows,
        columns=columns,
    )