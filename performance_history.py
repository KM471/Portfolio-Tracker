import pandas as pd

from account_history import get_account_history
from benchmark import get_benchmark_history


# ============================================================
# COMBINED PERFORMANCE HISTORY
# ============================================================

def get_performance_history(
    force_refresh=False,
):
    account = get_account_history(
        force_refresh=force_refresh,
    ).copy()

    benchmark = get_benchmark_history(
        force_refresh=force_refresh,
    ).copy()

    if account.empty:
        raise ValueError(
            "Account history is empty."
        )

    if benchmark.empty:
        raise ValueError(
            "Benchmark history is empty."
        )

    account["date"] = pd.to_datetime(
        account["date"],
        errors="coerce",
    ).dt.normalize()

    benchmark["date"] = pd.to_datetime(
        benchmark["date"],
        errors="coerce",
    ).dt.normalize()

    account = account.rename(
        columns={
            "invested_value_eur":
                "holdings_value_eur",
            "account_value_eur":
                "portfolio_value_eur",
        }
    )

    history = pd.merge(
        account,
        benchmark[
            [
                "date",
                "benchmark_value_eur",
                "benchmark_units",
                "benchmark_price_eur",
                "benchmark_flow_eur",
                "benchmark_gain_eur",
            ]
        ],
        on="date",
        how="inner",
    )

    history = (
        history
        .sort_values("date")
        .reset_index(drop=True)
    )

    # Profit is account NAV minus net external capital.
    # Cash left inside the brokerage remains part of NAV, so
    # selling investments does not create a fake loss.
    history["portfolio_gain_eur"] = (
        history["portfolio_value_eur"]
        - history["net_capital_invested_eur"]
    )

    history["portfolio_vs_benchmark_eur"] = (
        history["portfolio_value_eur"]
        - history["benchmark_value_eur"]
    )

    history["portfolio_peak_eur"] = (
        history["portfolio_value_eur"]
        .cummax()
    )

    history["benchmark_peak_eur"] = (
        history["benchmark_value_eur"]
        .cummax()
    )

    history["capital_peak_eur"] = (
        history["net_capital_invested_eur"]
        .cummax()
    )

    # Helpful diagnostic / allocation field.
    history["cash_weight_pct"] = 0.0

    positive_nav = (
        history["portfolio_value_eur"] > 0
    )

    history.loc[
        positive_nav,
        "cash_weight_pct",
    ] = (
        history.loc[
            positive_nav,
            "cash_balance_eur",
        ]
        / history.loc[
            positive_nav,
            "portfolio_value_eur",
        ]
        * 100.0
    )

    return history
