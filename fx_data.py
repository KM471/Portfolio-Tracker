from pathlib import Path
import time

import pandas as pd
import yfinance as yf


CACHE_DIRECTORY = (
    Path.home()
    / ".portfolio_intelligence_cache"
    / "fx_rates"
)

CACHE_LIFETIME_SECONDS = 60 * 60 * 6

COVERAGE_TOLERANCE_DAYS = 7


# Yahoo symbols are quoted as:
#
# 1 EUR = X units of the foreign currency.
#
# We invert the downloaded value later so that:
#
# 1 unit of foreign currency = X EUR.
FX_SYMBOLS = {
    "USD": "EURUSD=X",
    "GBP": "EURGBP=X",
    "CAD": "EURCAD=X",
    "CHF": "EURCHF=X",
}


# ============================================================
# CACHE HELPERS
# ============================================================

def _cache_path(
    currency,
):
    CACHE_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    return (
        CACHE_DIRECTORY
        / f"{currency}_EUR.csv"
    )


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

    cached["rate_to_eur"] = (
        pd.to_numeric(
            cached[
                "rate_to_eur"
            ],
            errors="coerce",
        )
    )

    cached = cached.dropna(
        subset=[
            "date",
            "currency",
            "rate_to_eur",
        ]
    )

    return (
        cached
        .sort_values(
            "date"
        )
        .drop_duplicates(
            subset=[
                "date",
                "currency",
            ],
            keep="last",
        )
        .reset_index(
            drop=True
        )
    )


def _cache_covers_start_date(
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

    return (
        pd.notna(
            earliest_cached_date
        )
        and earliest_cached_date
        <= tolerance_end
    )


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

    merged["rate_to_eur"] = (
        pd.to_numeric(
            merged[
                "rate_to_eur"
            ],
            errors="coerce",
        )
    )

    merged = merged.dropna(
        subset=[
            "date",
            "currency",
            "rate_to_eur",
        ]
    )

    return (
        merged
        .sort_values(
            "date"
        )
        .drop_duplicates(
            subset=[
                "date",
                "currency",
            ],
            keep="last",
        )
        .reset_index(
            drop=True
        )
    )


# ============================================================
# FX DOWNLOAD
# ============================================================

def _download_fx_history(
    currency,
    start_date,
):
    currency = (
        str(currency)
        .strip()
        .upper()
    )

    requested_start = (
        _normalise_start_date(
            start_date
        )
    )

    # EUR requires no conversion.
    if currency == "EUR":
        dates = pd.date_range(
            start=requested_start,
            end=pd.Timestamp.today(),
            freq="D",
        )

        return pd.DataFrame(
            {
                "date": dates,
                "currency": "EUR",
                "rate_to_eur": 1.0,
            }
        )

    if currency not in FX_SYMBOLS:
        raise KeyError(
            "No FX mapping exists for "
            f"{currency}"
        )

    yahoo_symbol = (
        FX_SYMBOLS[
            currency
        ]
    )

    ticker = yf.Ticker(
        yahoo_symbol
    )

    history = ticker.history(
        start=(
            requested_start.strftime(
                "%Y-%m-%d"
            )
        ),
        auto_adjust=False,
    )

    if history.empty:
        raise ValueError(
            "Yahoo returned no FX history for "
            f"{currency} "
            f"({yahoo_symbol})"
        )

    history = (
        history
        .reset_index()
        .rename(
            columns={
                "Date": "date",
                "Close":
                    "eur_to_currency",
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

    history[
        "eur_to_currency"
    ] = pd.to_numeric(
        history[
            "eur_to_currency"
        ],
        errors="coerce",
    )

    history = history.dropna(
        subset=[
            "date",
            "eur_to_currency",
        ]
    )

    history = history[
        history[
            "eur_to_currency"
        ] > 0
    ].copy()

    # Yahoo gives:
    #
    # 1 EUR = X USD / GBP / CAD / CHF
    #
    # We want:
    #
    # 1 USD / GBP / CAD / CHF = X EUR
    history[
        "rate_to_eur"
    ] = (
        1.0
        / history[
            "eur_to_currency"
        ]
    )

    history[
        "currency"
    ] = currency

    return (
        history[
            [
                "date",
                "currency",
                "rate_to_eur",
            ]
        ]
        .sort_values(
            "date"
        )
        .drop_duplicates(
            subset=[
                "date",
                "currency",
            ],
            keep="last",
        )
        .reset_index(
            drop=True
        )
    )


# ============================================================
# PUBLIC FX HISTORY
# ============================================================

def get_fx_history(
    currency,
    start_date="2025-07-01",
    force_refresh=False,
    max_age_seconds=(
        CACHE_LIFETIME_SECONDS
    ),
):
    currency = (
        str(currency)
        .strip()
        .upper()
    )

    requested_start = (
        _normalise_start_date(
            start_date
        )
    )

    if currency == "EUR":
        return _download_fx_history(
            currency,
            requested_start,
        )

    path = _cache_path(
        currency
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
            cached,
            requested_start,
        )
    )

    # Reuse only if the file is both fresh and covers the
    # required historical start date.
    if (
        not force_refresh
        and cache_fresh
        and cache_has_coverage
    ):
        return cached

    fresh = _download_fx_history(
        currency,
        requested_start,
    )

    # Merge rather than overwrite so running a shorter-history
    # account later cannot delete older FX observations needed by
    # another account.
    merged = _merge_histories(
        cached,
        fresh,
    )

    merged.to_csv(
        path,
        index=False,
    )

    return merged


def get_all_fx_history(
    currencies,
    start_date="2025-07-01",
    force_refresh=False,
):
    histories = []

    normalised_currencies = {
        str(currency)
        .strip()
        .upper()
        for currency in currencies
        if pd.notna(currency)
    }

    for currency in sorted(
        normalised_currencies
    ):
        history = get_fx_history(
            currency,
            start_date=start_date,
            force_refresh=force_refresh,
        )

        histories.append(
            history
        )

    if not histories:
        return pd.DataFrame(
            columns=[
                "date",
                "currency",
                "rate_to_eur",
            ]
        )

    return pd.concat(
        histories,
        ignore_index=True,
    )