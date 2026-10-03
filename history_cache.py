import hashlib
import os
import time
from pathlib import Path

import pandas as pd

from trading212 import (
    get_all_dividends,
    get_all_orders,
    get_all_transactions,
)


CACHE_ROOT = (
    Path.home()
    / ".portfolio_intelligence_cache"
    / "history"
)

CACHE_LIFETIME_SECONDS = 60 * 60


# ============================================================
# Account-specific cache
# ============================================================

def _account_cache_id():
    """
    Create a stable, non-reversible identifier for the
    currently configured Trading 212 account.

    The real API key is never written to disk.
    """

    api_key = str(
        os.getenv(
            "TRADING212_API_KEY",
            "",
        )
    ).strip()

    base_url = str(
        os.getenv(
            "TRADING212_BASE_URL",
            "",
        )
    ).strip()

    if not api_key:
        raise RuntimeError(
            "TRADING212_API_KEY is missing, so an "
            "account-specific history cache cannot be created."
        )

    fingerprint_source = (
        f"{base_url}|{api_key}"
    )

    return hashlib.sha256(
        fingerprint_source.encode(
            "utf-8"
        )
    ).hexdigest()[:16]


def _account_cache_directory():
    """
    Return the cache directory belonging to the
    currently configured Trading 212 account.
    """

    directory = (
        CACHE_ROOT
        / _account_cache_id()
    )

    directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    return directory


def _cache_path(name):
    return (
        _account_cache_directory()
        / f"{name}.json"
    )


# ============================================================
# Cache helpers
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


def _save_dataframe(
    dataframe,
    path,
):
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
    path = _cache_path(
        name
    )

    if (
        not force_refresh
        and _cache_is_fresh(
            path,
            max_age_seconds,
        )
    ):
        try:
            return _load_dataframe(
                path
            )

        except (
            ValueError,
            OSError,
        ):
            pass

    fresh_data = (
        fetch_function()
    )

    _save_dataframe(
        fresh_data,
        path,
    )

    return fresh_data


# ============================================================
# Public history functions
# ============================================================

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
    transactions = (
        get_cached_transactions(
            force_refresh=force_refresh,
        )
    )

    orders = (
        get_cached_orders(
            force_refresh=force_refresh,
        )
    )

    dividends = (
        get_cached_dividends(
            force_refresh=force_refresh,
        )
    )

    return (
        transactions,
        orders,
        dividends,
    )


# ============================================================
# Cache clearing
# ============================================================

def clear_history_cache():
    """
    Clear cached history only for the currently
    configured Trading 212 account.
    """

    directory = (
        _account_cache_directory()
    )

    for name in (
        "transactions",
        "orders",
        "dividends",
    ):
        path = (
            directory
            / f"{name}.json"
        )

        if path.exists():
            path.unlink()

    try:
        directory.rmdir()

    except OSError:
        pass