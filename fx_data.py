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


FX_SYMBOLS = {
    "USD": "EURUSD=X",
    "GBP": "EURGBP=X",
    "CAD": "EURCAD=X",
}


def _cache_path(currency):
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

    return age_seconds < max_age_seconds


def _download_fx_history(
    currency,
    start_date,
):
    if currency == "EUR":

        dates = pd.date_range(
            start=start_date,
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

    yahoo_symbol = FX_SYMBOLS[
        currency
    ]

    ticker = yf.Ticker(
        yahoo_symbol
    )

    history = ticker.history(
        start=start_date,
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
                "Close": "eur_to_currency",
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

    history["eur_to_currency"] = (
        pd.to_numeric(
            history["eur_to_currency"],
            errors="coerce",
        )
    )

    history = history.dropna(
        subset=[
            "date",
            "eur_to_currency",
        ]
    )

    history = history[
        history["eur_to_currency"] > 0
    ].copy()

    history["rate_to_eur"] = (
        1.0
        / history["eur_to_currency"]
    )

    history["currency"] = currency

    return history[
        [
            "date",
            "currency",
            "rate_to_eur",
        ]
    ]


def get_fx_history(
    currency,
    start_date="2025-07-01",
    force_refresh=False,
    max_age_seconds=CACHE_LIFETIME_SECONDS,
):
    if currency == "EUR":
        return _download_fx_history(
            currency,
            start_date,
        )

    path = _cache_path(
        currency
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

    history = _download_fx_history(
        currency,
        start_date,
    )

    history.to_csv(
        path,
        index=False,
    )

    return history


def get_all_fx_history(
    currencies,
    start_date="2025-07-01",
    force_refresh=False,
):
    histories = []

    for currency in sorted(
        set(currencies)
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
        return pd.DataFrame()

    return pd.concat(
        histories,
        ignore_index=True,
    )