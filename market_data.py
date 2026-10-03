from pathlib import Path
import json
import time

import pandas as pd
import yfinance as yf

from ticker_resolver import resolve_yahoo_ticker
from trading212 import get_instrument_metadata


CACHE_DIRECTORY = (
    Path.home()
    / ".portfolio_intelligence_cache"
    / "market_prices"
)

CACHE_LIFETIME_SECONDS = 60 * 60 * 6

# Allows for weekends / market holidays when checking whether
# the first returned market observation is close enough to the
# requested start date.
COVERAGE_TOLERANCE_DAYS = 7


# ============================================================
# CACHE PATHS
# ============================================================

def _cache_path(
    trading212_ticker,
):
    CACHE_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    safe_name = (
        trading212_ticker.replace(
            "/",
            "_",
        )
    )

    return (
        CACHE_DIRECTORY
        / f"{safe_name}.csv"
    )


def _cache_metadata_path(
    trading212_ticker,
):
    CACHE_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    safe_name = (
        trading212_ticker.replace(
            "/",
            "_",
        )
    )

    return (
        CACHE_DIRECTORY
        / f"{safe_name}.meta.json"
    )


# ============================================================
# CACHE HELPERS
# ============================================================

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

    return (
        age_seconds
        < max_age_seconds
    )


def _normalise_start_date(
    value,
):
    return (
        pd.Timestamp(value)
        .normalize()
    )


def _load_cached_history(
    path,
):
    if not path.exists():
        return pd.DataFrame()

    try:
        cached = pd.read_csv(
            path,
            parse_dates=[
                "date",
            ],
        )

    except (
        ValueError,
        OSError,
    ):
        return pd.DataFrame()

    if cached.empty:
        return cached

    cached["date"] = pd.to_datetime(
        cached["date"],
        errors="coerce",
    )

    if cached["date"].dt.tz is not None:
        cached["date"] = (
            cached["date"]
            .dt.tz_localize(None)
        )

    cached["date"] = (
        cached["date"]
        .dt.normalize()
    )

    if "close" in cached.columns:
        cached["close"] = pd.to_numeric(
            cached["close"],
            errors="coerce",
        )

    cached = cached.dropna(
        subset=[
            "date",
            "close",
        ]
    )

    duplicate_columns = [
        "date",
    ]

    if (
        "trading212_ticker"
        in cached.columns
    ):
        duplicate_columns.append(
            "trading212_ticker"
        )

    return (
        cached
        .sort_values(
            "date"
        )
        .drop_duplicates(
            subset=duplicate_columns,
            keep="last",
        )
        .reset_index(
            drop=True
        )
    )


def _load_cache_coverage(
    trading212_ticker,
):
    path = _cache_metadata_path(
        trading212_ticker
    )

    if not path.exists():
        return None

    try:
        with path.open(
            "r",
            encoding="utf-8",
        ) as file:
            metadata = json.load(
                file
            )

        value = metadata.get(
            "earliest_requested_start"
        )

        if not value:
            return None

        return (
            pd.Timestamp(value)
            .normalize()
        )

    except (
        ValueError,
        TypeError,
        OSError,
        json.JSONDecodeError,
    ):
        return None


def _save_cache_coverage(
    trading212_ticker,
    coverage_start,
):
    path = _cache_metadata_path(
        trading212_ticker
    )

    coverage_start = (
        pd.Timestamp(
            coverage_start
        )
        .normalize()
    )

    metadata = {
        "earliest_requested_start":
            coverage_start.strftime(
                "%Y-%m-%d"
            )
    }

    with path.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            metadata,
            file,
            indent=2,
        )


def _cache_covers_start_date(
    trading212_ticker,
    cached,
    requested_start,
):
    if cached.empty:
        return False

    requested_start = (
        _normalise_start_date(
            requested_start
        )
    )

    # Preferred method:
    # metadata records the earliest date Yahoo has already been
    # asked to provide for this instrument.
    coverage_start = (
        _load_cache_coverage(
            trading212_ticker
        )
    )

    if (
        coverage_start is not None
        and coverage_start
        <= requested_start
    ):
        return True

    # Backwards compatibility for cache files created before
    # coverage metadata existed.
    #
    # A few days' difference is acceptable because weekends
    # and market holidays may mean the first actual price is
    # later than the requested calendar date.
    earliest_cached_date = (
        cached["date"]
        .min()
    )

    tolerance_end = (
        requested_start
        + pd.Timedelta(
            days=COVERAGE_TOLERANCE_DAYS
        )
    )

    if (
        pd.notna(
            earliest_cached_date
        )
        and earliest_cached_date
        <= tolerance_end
    ):
        # Record the requested start so future checks do not need
        # to infer coverage from the first market observation.
        _save_cache_coverage(
            trading212_ticker,
            requested_start,
        )

        return True

    return False


def _merge_histories(
    cached,
    fresh,
):
    if cached.empty:
        merged = fresh.copy()

    elif fresh.empty:
        merged = cached.copy()

    else:
        merged = pd.concat(
            [
                cached,
                fresh,
            ],
            ignore_index=True,
        )

    if merged.empty:
        return merged

    merged["date"] = pd.to_datetime(
        merged["date"],
        errors="coerce",
    )

    if merged["date"].dt.tz is not None:
        merged["date"] = (
            merged["date"]
            .dt.tz_localize(None)
        )

    merged["date"] = (
        merged["date"]
        .dt.normalize()
    )

    merged["close"] = pd.to_numeric(
        merged["close"],
        errors="coerce",
    )

    merged = merged.dropna(
        subset=[
            "date",
            "close",
        ]
    )

    duplicate_columns = [
        "date",
    ]

    if (
        "trading212_ticker"
        in merged.columns
    ):
        duplicate_columns.append(
            "trading212_ticker"
        )

    return (
        merged
        .sort_values(
            "date"
        )
        .drop_duplicates(
            subset=duplicate_columns,
            keep="last",
        )
        .reset_index(
            drop=True
        )
    )


# ============================================================
# CURRENCY NORMALISATION
# ============================================================

def _normalise_currency(
    currency_code,
):
    if currency_code == "GBX":
        return "GBP", 0.01

    return (
        currency_code,
        1.0,
    )


# ============================================================
# YAHOO DOWNLOAD
# ============================================================

def _download_price_history(
    trading212_ticker,
    start_date,
):
    metadata = (
        get_instrument_metadata()
    )

    instrument = metadata.get(
        trading212_ticker,
        {},
    )

    source_currency = (
        instrument.get(
            "currencyCode"
        )
    )

    if not source_currency:
        raise ValueError(
            "No currency metadata "
            "found for "
            f"{trading212_ticker}"
        )

    yahoo_ticker = (
        resolve_yahoo_ticker(
            trading212_ticker,
            instrument=instrument,
        )
    )

    (
        normalised_currency,
        price_multiplier,
    ) = _normalise_currency(
        source_currency
    )

    ticker = yf.Ticker(
        yahoo_ticker
    )

    history = ticker.history(
        start=(
            pd.Timestamp(
                start_date
            )
            .strftime(
                "%Y-%m-%d"
            )
        ),
        auto_adjust=False,
        actions=True,
    )

    if history.empty:
        raise ValueError(
            "Yahoo returned no price "
            "history for "
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
                "Dividends":
                    "dividends",
                "Stock Splits":
                    "stock_splits",
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

    if (
        "dividends"
        in history.columns
    ):
        history["dividends"] = (
            pd.to_numeric(
                history[
                    "dividends"
                ],
                errors="coerce",
            )
            .fillna(
                0.0
            )
            * price_multiplier
        )

    else:
        history["dividends"] = 0.0

    if (
        "stock_splits"
        in history.columns
    ):
        history["stock_splits"] = (
            pd.to_numeric(
                history[
                    "stock_splits"
                ],
                errors="coerce",
            )
            .fillna(
                0.0
            )
        )

    else:
        history["stock_splits"] = 0.0

    history[
        "trading212_ticker"
    ] = trading212_ticker

    history[
        "yahoo_ticker"
    ] = yahoo_ticker

    history[
        "source_currency"
    ] = source_currency

    history[
        "currency"
    ] = normalised_currency

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

    return (
        history
        .sort_values(
            "date"
        )
        .drop_duplicates(
            subset=[
                "date",
                "trading212_ticker",
            ],
            keep="last",
        )
        .reset_index(
            drop=True
        )
    )


# ============================================================
# PUBLIC PRICE HISTORY
# ============================================================

def get_price_history(
    trading212_ticker,
    start_date="2025-07-01",
    force_refresh=False,
    max_age_seconds=(
        CACHE_LIFETIME_SECONDS
    ),
):
    requested_start = (
        _normalise_start_date(
            start_date
        )
    )

    path = _cache_path(
        trading212_ticker
    )

    cached = (
        _load_cached_history(
            path
        )
    )

    cache_fresh = (
        _cache_is_fresh(
            path,
            max_age_seconds,
        )
    )

    cache_has_coverage = (
        _cache_covers_start_date(
            trading212_ticker,
            cached,
            requested_start,
        )
    )

    # A cached file is reusable only when BOTH conditions hold:
    #
    # 1. it is recent enough;
    # 2. it covers the historical range being requested.
    if (
        not force_refresh
        and cache_fresh
        and cache_has_coverage
    ):
        return cached

    # Download from the requested start date.
    #
    # Existing older cached observations are merged back in so
    # refreshing a shorter-history account cannot truncate the
    # history previously downloaded for a longer-history account.
    fresh = _download_price_history(
        trading212_ticker,
        requested_start,
    )

    merged = _merge_histories(
        cached,
        fresh,
    )

    merged.to_csv(
        path,
        index=False,
    )

    # Determine what historical start the cache is known to cover.
    previous_coverage = None

    if not cached.empty:
        previous_coverage = (
            _load_cache_coverage(
                trading212_ticker
            )
        )

        if previous_coverage is None:
            previous_coverage = (
                cached["date"]
                .min()
            )

    if previous_coverage is None:
        new_coverage = requested_start

    else:
        new_coverage = min(
            previous_coverage,
            requested_start,
        )

    _save_cache_coverage(
        trading212_ticker,
        new_coverage,
    )

    return merged


def get_all_price_history(
    trading212_tickers,
    start_date="2025-07-01",
    force_refresh=False,
):
    histories = []

    for trading212_ticker in (
        trading212_tickers
    ):
        history = (
            get_price_history(
                trading212_ticker,
                start_date=start_date,
                force_refresh=force_refresh,
            )
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