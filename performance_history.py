import pandas as pd

from account_history import get_account_history
from benchmark import get_benchmark_history


# ============================================================
# COMBINED PERFORMANCE HISTORY
# ============================================================

def get_performance_history(
    force_refresh=False,
):

    # --------------------------------------------------------
    # Actual account history
    #
    # Includes:
    # - holdings
    # - cash
    # - deposits / withdrawals
    # - dividends
    # --------------------------------------------------------

    account = get_account_history(
        force_refresh=force_refresh,
    ).copy()

    # --------------------------------------------------------
    # Counterfactual S&P 500 portfolio
    # --------------------------------------------------------

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

    # ========================================================
    # NORMALISE DATES
    # ========================================================

    account["date"] = (
        pd.to_datetime(
            account["date"],
            errors="coerce",
        )
        .dt.normalize()
    )

    benchmark["date"] = (
        pd.to_datetime(
            benchmark["date"],
            errors="coerce",
        )
        .dt.normalize()
    )

    # ========================================================
    # CLEARER NAMES
    # ========================================================

    account = account.rename(
        columns={
            "invested_value_eur":
                "holdings_value_eur",

            "account_value_eur":
                "portfolio_value_eur",
        }
    )

    # ========================================================
    # MERGE
    # ========================================================

    history = pd.merge(
        account,
        benchmark[
            [
                "date",
                "benchmark_value_eur",
                "benchmark_units",
                "benchmark_price_eur",
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

    # ========================================================
    # BENCHMARK CASH FLOW
    #
    # Your benchmark rule:
    #
    # Buy €X stock  -> buy €X S&P 500
    # Sell €X stock -> sell €X S&P 500
    # ========================================================

    history[
        "benchmark_flow_eur"
    ] = (
        history[
            "gross_buys_eur"
        ]
        -
        history[
            "gross_sells_eur"
        ]
    )

    # ========================================================
    # ACCOUNT PROFIT
    # ========================================================

    history[
        "portfolio_gain_eur"
    ] = (
        history[
            "portfolio_value_eur"
        ]
        -
        history[
            "net_capital_invested_eur"
        ]
    )

    # ========================================================
    # PORTFOLIO VS BENCHMARK
    # ========================================================

    history[
        "portfolio_vs_benchmark_eur"
    ] = (
        history[
            "portfolio_value_eur"
        ]
        -
        history[
            "benchmark_value_eur"
        ]
    )

    # ========================================================
    # PEAK VALUES
    # ========================================================

    history[
        "portfolio_peak_eur"
    ] = (
        history[
            "portfolio_value_eur"
        ]
        .cummax()
    )

    history[
        "benchmark_peak_eur"
    ] = (
        history[
            "benchmark_value_eur"
        ]
        .cummax()
    )

    history[
        "capital_peak_eur"
    ] = (
        history[
            "net_capital_invested_eur"
        ]
        .cummax()
    )

    return history