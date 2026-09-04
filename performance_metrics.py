import pandas as pd

from performance_history import get_performance_history


# ============================================================
# PERFORMANCE METRICS
# ============================================================

def get_performance_metrics(
    force_refresh=False,
):

    history = (
        get_performance_history(
            force_refresh=force_refresh,
        )
        .copy()
    )

    if history.empty:
        raise ValueError(
            "Performance history is empty."
        )

    history = (
        history
        .sort_values("date")
        .reset_index(drop=True)
    )

    # ========================================================
    # NUMERIC CLEANING
    # ========================================================

    numeric_columns = [
        "portfolio_value_eur",
        "benchmark_value_eur",
        "external_flow_eur",
        "benchmark_flow_eur",
        "net_capital_invested_eur",
    ]

    for column in numeric_columns:

        history[column] = (
            pd.to_numeric(
                history[column],
                errors="coerce",
            )
            .fillna(0.0)
        )

    # ========================================================
    # PREVIOUS VALUES
    # ========================================================

    history[
        "previous_portfolio_value_eur"
    ] = (
        history[
            "portfolio_value_eur"
        ]
        .shift(1)
    )

    history[
        "previous_benchmark_value_eur"
    ] = (
        history[
            "benchmark_value_eur"
        ]
        .shift(1)
    )

    # ========================================================
    # PORTFOLIO DAILY TWR
    #
    # IMPORTANT:
    #
    # BUY / SELL trades are INTERNAL movements.
    #
    # Only deposits and withdrawals are external flows.
    #
    # Daily return:
    #
    # (Ending Value - External Flow)
    # -------------------------------- - 1
    # Beginning Value
    #
    # This assumes daily cash flows occur at the end of the
    # valuation period. With daily market data this is a
    # sensible approximation.
    # ========================================================

    history[
        "portfolio_daily_return"
    ] = 0.0

    portfolio_valid = (
        history[
            "previous_portfolio_value_eur"
        ]
        > 0
    )

    history.loc[
        portfolio_valid,
        "portfolio_daily_return",
    ] = (

        (
            history.loc[
                portfolio_valid,
                "portfolio_value_eur",
            ]
            -
            history.loc[
                portfolio_valid,
                "external_flow_eur",
            ]
        )

        /

        history.loc[
            portfolio_valid,
            "previous_portfolio_value_eur",
        ]

        - 1.0
    )

    # ========================================================
    # BENCHMARK DAILY TWR
    #
    # Benchmark rule:
    #
    # Actual BUY €X  -> S&P receives €X
    # Actual SELL €X -> S&P removes €X
    #
    # Therefore benchmark_flow_eur is the external flow for
    # the synthetic benchmark portfolio.
    # ========================================================

    history[
        "benchmark_daily_return"
    ] = 0.0

    benchmark_valid = (
        history[
            "previous_benchmark_value_eur"
        ]
        > 0
    )

    history.loc[
        benchmark_valid,
        "benchmark_daily_return",
    ] = (

        (
            history.loc[
                benchmark_valid,
                "benchmark_value_eur",
            ]
            -
            history.loc[
                benchmark_valid,
                "benchmark_flow_eur",
            ]
        )

        /

        history.loc[
            benchmark_valid,
            "previous_benchmark_value_eur",
        ]

        - 1.0
    )

    # ========================================================
    # CUMULATIVE TIME-WEIGHTED RETURN
    # ========================================================

    history[
        "portfolio_growth_index"
    ] = (
        1.0
        + history[
            "portfolio_daily_return"
        ]
    ).cumprod()

    history[
        "benchmark_growth_index"
    ] = (
        1.0
        + history[
            "benchmark_daily_return"
        ]
    ).cumprod()

    history[
        "portfolio_twr_pct"
    ] = (
        history[
            "portfolio_growth_index"
        ]
        - 1.0
    ) * 100

    history[
        "benchmark_twr_pct"
    ] = (
        history[
            "benchmark_growth_index"
        ]
        - 1.0
    ) * 100

    # ========================================================
    # RELATIVE PERFORMANCE
    # ========================================================

    history[
        "relative_growth_index"
    ] = (
        history[
            "portfolio_growth_index"
        ]
        /
        history[
            "benchmark_growth_index"
        ]
    )

    history[
        "relative_return_pct"
    ] = (
        history[
            "relative_growth_index"
        ]
        - 1.0
    ) * 100

    history[
        "relative_return_pp"
    ] = (
        history[
            "portfolio_twr_pct"
        ]
        -
        history[
            "benchmark_twr_pct"
        ]
    )

    # ========================================================
    # SIMPLE ACCOUNT RETURN
    #
    # Useful alongside TWR, but NOT a substitute for TWR.
    # ========================================================

    history[
        "simple_gain_eur"
    ] = (
        history[
            "portfolio_value_eur"
        ]
        -
        history[
            "net_capital_invested_eur"
        ]
    )

    history[
        "simple_return_pct"
    ] = 0.0

    capital_valid = (
        history[
            "net_capital_invested_eur"
        ]
        > 0
    )

    history.loc[
        capital_valid,
        "simple_return_pct",
    ] = (

        history.loc[
            capital_valid,
            "simple_gain_eur",
        ]

        /

        history.loc[
            capital_valid,
            "net_capital_invested_eur",
        ]

        * 100
    )

    # ========================================================
    # DRAWDOWN
    #
    # Use TWR growth indices rather than raw account value.
    #
    # Therefore withdrawing €1,000 does NOT appear as a
    # massive investment loss.
    # ========================================================

    history[
        "portfolio_peak_index"
    ] = (
        history[
            "portfolio_growth_index"
        ]
        .cummax()
    )

    history[
        "benchmark_peak_index"
    ] = (
        history[
            "benchmark_growth_index"
        ]
        .cummax()
    )

    history[
        "portfolio_drawdown_pct"
    ] = (

        history[
            "portfolio_growth_index"
        ]

        /

        history[
            "portfolio_peak_index"
        ]

        - 1.0

    ) * 100

    history[
        "benchmark_drawdown_pct"
    ] = (

        history[
            "benchmark_growth_index"
        ]

        /

        history[
            "benchmark_peak_index"
        ]

        - 1.0

    ) * 100

    # ========================================================
    # SUMMARY
    # ========================================================

    latest = history.iloc[-1]

    summary = {

        "portfolio_value_eur":
            float(
                latest[
                    "portfolio_value_eur"
                ]
            ),

        "benchmark_value_eur":
            float(
                latest[
                    "benchmark_value_eur"
                ]
            ),

        "net_capital_invested_eur":
            float(
                latest[
                    "net_capital_invested_eur"
                ]
            ),

        "simple_gain_eur":
            float(
                latest[
                    "simple_gain_eur"
                ]
            ),

        "simple_return_pct":
            float(
                latest[
                    "simple_return_pct"
                ]
            ),

        "portfolio_twr_pct":
            float(
                latest[
                    "portfolio_twr_pct"
                ]
            ),

        "benchmark_twr_pct":
            float(
                latest[
                    "benchmark_twr_pct"
                ]
            ),

        "relative_return_pct":
            float(
                latest[
                    "relative_return_pct"
                ]
            ),

        "relative_return_pp":
            float(
                latest[
                    "relative_return_pp"
                ]
            ),

        "portfolio_max_drawdown_pct":
            float(
                history[
                    "portfolio_drawdown_pct"
                ]
                .min()
            ),

        "benchmark_max_drawdown_pct":
            float(
                history[
                    "benchmark_drawdown_pct"
                ]
                .min()
            ),

        "peak_net_capital_eur":
            float(
                history[
                    "net_capital_invested_eur"
                ]
                .max()
            ),

        "worst_portfolio_day_pct":
            float(
                history[
                    "portfolio_daily_return"
                ]
                .min()
                * 100
            ),

        "best_portfolio_day_pct":
            float(
                history[
                    "portfolio_daily_return"
                ]
                .max()
                * 100
            ),
    }

    return history, summary