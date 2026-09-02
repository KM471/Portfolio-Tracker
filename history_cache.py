from pathlib import Path
import time

import pandas as pd

from trading212 import (
    get_all_dividends,
    get_all_orders,
    get_all_transactions,
)


CACHE_DIRECTORY = (
    Path.home()
    / ".portfolio_intelligence_cache"
)

CACHE_LIFETIME_SECONDS = 60 * 60


def _cache_path(name):
    CACHE_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    return CACHE_DIRECTORY / f"{name}.json"


def _cache_is_fresh(path, max_age_seconds):
    if not path.exists():
        return False

    age_seconds = (
        time.time()
        - path.stat().st_mtime
    )

    return age_seconds < max_age_seconds


def _save_dataframe(dataframe, path):
    dataframe.to_json(
        path,
        orient="records",
        date_format="iso",
    )


def _load_dataframe(path):
    return pd.read_json(
        path,
        orient="records",
    )


def _get_cached_data(
    name,
    fetch_function,
    force_refresh=False,
    max_age_seconds=CACHE_LIFETIME_SECONDS,
):
    path = _cache_path(name)

    if (
        not force_refresh
        and _cache_is_fresh(
            path,
            max_age_seconds,
        )
    ):
        try:
            return _load_dataframe(path)

        except (ValueError, OSError):
            pass

    fresh_data = fetch_function()

    _save_dataframe(
        fresh_data,
        path,
    )

    return fresh_data


def get_cached_transactions(
    force_refresh=False,
):
    return _get_cached_data(
        "transactions",
        get_all_transactions,
        force_refresh=force_refresh,
    )


def get_cached_orders(
    force_refresh=False,
):
    return _get_cached_data(
        "orders",
        get_all_orders,
        force_refresh=force_refresh,
    )


def get_cached_dividends(
    force_refresh=False,
):
    return _get_cached_data(
        "dividends",
        get_all_dividends,
        force_refresh=force_refresh,
    )


def get_cached_history(
    force_refresh=False,
):
    transactions = get_cached_transactions(
        force_refresh=force_refresh,
    )

    orders = get_cached_orders(
        force_refresh=force_refresh,
    )

    dividends = get_cached_dividends(
        force_refresh=force_refresh,
    )

    return transactions, orders, dividends


def clear_history_cache():
    for name in (
        "transactions",
        "orders",
        "dividends",
    ):
        path = _cache_path(name)

        if path.exists():
            path.unlink()