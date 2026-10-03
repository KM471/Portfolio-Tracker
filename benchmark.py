from pathlib import Path

import pandas as pd
import yfinance as yf

from history_cache import get_cached_transactions
from fx_data import get_all_fx_history


BENCHMARK_SYMBOL = "SPY"

CACHE_DIR = (
    Path.home()
    / ".portfolio_intelligence_cache"
)

CACHE_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

BENCHMARK_CACHE_FILE = (
    CACHE_DIR
    / "spy_benchmark.csv"
)


# ============================================================
# EXTERNAL ACCOUNT FLOWS
# ============================================================

def _prepare_external_flows(
    force_refresh=False,
):
    transactions = (
        get_cached_transactions(
            force_refresh=force_refresh,
        )
        .copy()
    )

    empty = pd.DataFrame(
        columns=[
            "date",
            "benchmark_flow_eur",
        ]
    )

    if transactions.empty:
        return empty

    transactions["dateTime"] = pd.to_datetime(
        transactions["dateTime"],
        utc=True,
        errors="coerce",
    )

    transactions["date"] = (
        transactions["dateTime"]
        .dt.tz_convert(None)
        .dt.normalize()
    )

    transactions["amount"] = pd.to_numeric(
        transactions["amount"],
        errors="coerce",
    )

    transactions["type"] = (
        transactions["type"]
        .astype(str)
        .str.upper()
    )

    if "currency" in transactions.columns:
        transactions["currency"] = (
            transactions["currency"]
            .astype(str)
            .str.upper()
        )

        non_eur = transactions[
            transactions["currency"] != "EUR"
        ]

        if not non_eur.empty:
            currencies = sorted(
                non_eur["currency"]
                .dropna()
                .unique()
                .tolist()
            )

            raise ValueError(
                "This dashboard currently expects a EUR "
                "Trading 212 account. Non-EUR external "
                f"transactions were found: {currencies}."
            )

    transactions = transactions[
        transactions["type"].isin(
            ["DEPOSIT", "WITHDRAW"]
        )
    ].dropna(
        subset=[
            "date",
            "amount",
        ]
    ).copy()

    if transactions.empty:
        return empty

    transactions["benchmark_flow_eur"] = 0.0

    deposit_mask = (
        transactions["type"] == "DEPOSIT"
    )

    withdraw_mask = (
        transactions["type"] == "WITHDRAW"
    )

    transactions.loc[
        deposit_mask,
        "benchmark_flow_eur",
    ] = (
        transactions.loc[
            deposit_mask,
            "amount",
        ]
        .abs()
    )

    transactions.loc[
        withdraw_mask,
        "benchmark_flow_eur",
    ] = -(
        transactions.loc[
            withdraw_mask,
            "amount",
        ]
        .abs()
    )

    return (
        transactions
        .groupby(
            "date",
            as_index=False,
        )["benchmark_flow_eur"]
        .sum()
        .sort_values("date")
        .reset_index(drop=True)
    )


# ============================================================
# S&P 500 PRICE HISTORY
# ============================================================

def _download_benchmark_prices(
    start_date,
    end_date,
):
    download_end = (
        pd.Timestamp(end_date)
        + pd.Timedelta(days=1)
    )

    raw = yf.download(
        BENCHMARK_SYMBOL,
        start=pd.Timestamp(
            start_date
        ).strftime("%Y-%m-%d"),
        end=download_end.strftime(
            "%Y-%m-%d"
        ),
        auto_adjust=True,
        progress=False,
    )

    if raw.empty:
        raise ValueError(
            "Yahoo Finance returned no "
            "S&P 500 benchmark data."
        )

    close = raw["Close"]

    if isinstance(
        close,
        pd.DataFrame,
    ):
        close = close.iloc[:, 0]

    history = pd.DataFrame(
        {
            "date": (
                pd.to_datetime(
                    close.index
                )
                .tz_localize(None)
                .normalize()
            ),
            "price_usd": pd.to_numeric(
                close.values,
                errors="coerce",
            ),
        }
    )

    history = (
        history
        .dropna()
        .drop_duplicates(
            subset=["date"],
            keep="last",
        )
        .sort_values("date")
        .reset_index(drop=True)
    )

    history.to_csv(
        BENCHMARK_CACHE_FILE,
        index=False,
    )

    return history


def _get_benchmark_prices(
    start_date,
    end_date,
    force_refresh=False,
):
    start_date = pd.Timestamp(
        start_date
    ).normalize()

    end_date = pd.Timestamp(
        end_date
    ).normalize()

    if (
        BENCHMARK_CACHE_FILE.exists()
        and not force_refresh
    ):
        try:
            cached = pd.read_csv(
                BENCHMARK_CACHE_FILE
            )

            cached["date"] = pd.to_datetime(
                cached["date"],
                errors="coerce",
            ).dt.normalize()

            cached["price_usd"] = pd.to_numeric(
                cached["price_usd"],
                errors="coerce",
            )

            cached = (
                cached
                .dropna()
                .sort_values("date")
            )

            if (
                not cached.empty
                and cached["date"].min()
                <= start_date
                and cached["date"].max()
                >= end_date
            ):
                return cached[
                    (cached["date"] >= start_date)
                    & (cached["date"] <= end_date)
                ].copy()

        except Exception:
            pass

    return _download_benchmark_prices(
        start_date,
        end_date,
    )


# ============================================================
# COUNTERFACTUAL S&P 500 PORTFOLIO
# ============================================================

def get_benchmark_history(
    force_refresh=False,
):
    flows = _prepare_external_flows(
        force_refresh=force_refresh,
    )

    if flows.empty:
        return pd.DataFrame()

    first_date = (
        flows["date"]
        .min()
        .normalize()
    )

    today = (
        pd.Timestamp.now(tz="UTC")
        .tz_convert(None)
        .normalize()
    )

    prices = _get_benchmark_prices(
        first_date,
        today,
        force_refresh=force_refresh,
    )

    last_date = (
        prices["date"]
        .max()
        .normalize()
    )

    fx = get_all_fx_history(
        ["USD"],
        start_date=first_date.strftime(
            "%Y-%m-%d"
        ),
        force_refresh=force_refresh,
    ).copy()

    fx["date"] = pd.to_datetime(
        fx["date"],
        errors="coerce",
    ).dt.normalize()

    fx["rate_to_eur"] = pd.to_numeric(
        fx["rate_to_eur"],
        errors="coerce",
    )

    fx = fx[
        fx["currency"] == "USD"
    ].copy()

    calendar = pd.date_range(
        first_date,
        last_date,
        freq="D",
    )

    price_series = (
        prices
        .set_index("date")["price_usd"]
        .reindex(calendar)
        .ffill()
        .bfill()
    )

    fx_series = (
        fx
        .set_index("date")["rate_to_eur"]
        .reindex(calendar)
        .ffill()
        .bfill()
    )

    price_eur = (
        price_series
        * fx_series
    )

    flow_series = (
        flows
        .set_index("date")
        ["benchmark_flow_eur"]
        .reindex(calendar)
        .fillna(0.0)
    )

    benchmark_units = 0.0
    net_contributed_eur = 0.0
    records = []

    for date in calendar:
        current_price_eur = float(
            price_eur.loc[date]
        )

        flow = float(
            flow_series.loc[date]
        )

        if current_price_eur <= 0:
            raise ValueError(
                "Benchmark price must be positive."
            )

        # Deposits buy benchmark units; withdrawals sell them.
        # Internal stock buys/sells in the real account are
        # deliberately ignored here.
        benchmark_units += (
            flow
            / current_price_eur
        )

        net_contributed_eur += flow

        benchmark_value_eur = (
            benchmark_units
            * current_price_eur
        )

        benchmark_gain_eur = (
            benchmark_value_eur
            - net_contributed_eur
        )

        records.append(
            {
                "date": date,
                "benchmark_price_eur": (
                    current_price_eur
                ),
                "benchmark_units": (
                    benchmark_units
                ),
                "benchmark_value_eur": (
                    benchmark_value_eur
                ),
                "benchmark_flow_eur": flow,
                "net_invested_eur": (
                    net_contributed_eur
                ),
                "benchmark_gain_eur": (
                    benchmark_gain_eur
                ),
            }
        )

    return pd.DataFrame(records)
