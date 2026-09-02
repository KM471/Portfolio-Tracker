from pathlib import Path
import time

import pandas as pd
import yfinance as yf

from market_symbols import TICKER_MAP
from trading212 import get_instrument_metadata


CACHE_DIRECTORY = (
    Path.home()
    / ".portfolio_intelligence_cache"
    / "market_prices"
)

CACHE_LIFETIME_SECONDS = 60 * 60 * 6


def _cache_path(trading212_ticker):
    CACHE_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    safe_name = trading212_ticker.replace(
        "/",
        "_",
    )

    return CACHE_DIRECTORY / f"{safe_name}.csv"


def _cache_is_fresh(
    path,
    max_age_seconds,
):
    if not path.exists():
        return False

    age_seconds = (
        time.time()
        - path.stat().st_mtime
    )

    return age_seconds < max_age_seconds


def _normalise_currency(currency_code):
    if currency_code == "GBX":
        return "GBP", 0.01

    return currency_code, 1.0


def _download_price_history(
    trading212_ticker,
    start_date,
):
    if trading212_ticker not in TICKER_MAP:
        raise KeyError(
            "No Yahoo mapping exists for "
            f"{trading212_ticker}"
        )

    yahoo_ticker = TICKER_MAP[
        trading212_ticker
    ]

    metadata = get_instrument_metadata()

    instrument = metadata.get(
        trading212_ticker,
        {},
    )

    source_currency = instrument.get(
        "currencyCode"
    )

    if not source_currency:
        raise ValueError(
            "No currency metadata found for "
            f"{trading212_ticker}"
        )

    normalised_currency, price_multiplier = (
        _normalise_currency(
            source_currency
        )
    )

    ticker = yf.Ticker(
        yahoo_ticker
    )

    history = ticker.history(
        start=start_date,
        auto_adjust=False,
        actions=True,
    )

    if history.empty:
        raise ValueError(
            "Yahoo returned no price history for "
            f"{trading212_ticker} "
            f"({yahoo_ticker})"
        )

    history = (
        history
        .reset_index()
        .rename(
            columns={
                "Date": "date",
                "Close": "close",
                "Dividends": "dividends",
                "Stock Splits": "stock_splits",
            }
        )
    )

    history["date"] = pd.to_datetime(
        history["date"],
        errors="coerce",
    )

    if history["date"].dt.tz is not None:
        history["date"] = (
            history["date"]
            .dt.tz_localize(None)
        )

    history["date"] = (
        history["date"]
        .dt.normalize()
    )

    history["close"] = (
        pd.to_numeric(
            history["close"],
            errors="coerce",
        )
        * price_multiplier
    )

    if "dividends" in history.columns:
        history["dividends"] = (
            pd.to_numeric(
                history["dividends"],
                errors="coerce",
            ).fillna(0)
            * price_multiplier
        )
    else:
        history["dividends"] = 0.0

    if "stock_splits" in history.columns:
        history["stock_splits"] = (
            pd.to_numeric(
                history["stock_splits"],
                errors="coerce",
            ).fillna(0)
        )
    else:
        history["stock_splits"] = 0.0

    history["trading212_ticker"] = (
        trading212_ticker
    )

    history["yahoo_ticker"] = (
        yahoo_ticker
    )

    history["source_currency"] = (
        source_currency
    )

    history["currency"] = (
        normalised_currency
    )

    history = history[
        [
            "date",
            "trading212_ticker",
            "yahoo_ticker",
            "close",
            "currency",
            "source_currency",
            "dividends",
            "stock_splits",
        ]
    ]

    history = history.dropna(
        subset=[
            "date",
            "close",
        ]
    )

    return history


def get_price_history(
    trading212_ticker,
    start_date="2025-07-01",
    force_refresh=False,
    max_age_seconds=CACHE_LIFETIME_SECONDS,
):
    path = _cache_path(
        trading212_ticker
    )

    if (
        not force_refresh
        and _cache_is_fresh(
            path,
            max_age_seconds,
        )
    ):
        try:
            cached = pd.read_csv(
                path,
                parse_dates=["date"],
            )

            if not cached.empty:
                return cached

        except (
            ValueError,
            OSError,
        ):
            pass

    history = _download_price_history(
        trading212_ticker,
        start_date,
    )

    history.to_csv(
        path,
        index=False,
    )

    return history


def get_all_price_history(
    trading212_tickers,
    start_date="2025-07-01",
    force_refresh=False,
):
    histories = []

    for trading212_ticker in trading212_tickers:
        history = get_price_history(
            trading212_ticker,
            start_date=start_date,
            force_refresh=force_refresh,
        )

        histories.append(
            history
        )

    if not histories:
        return pd.DataFrame()

    return pd.concat(
        histories,
        ignore_index=True,
    )