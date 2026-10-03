import numpy as np
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

    numeric_columns = [
        "portfolio_value_eur",
        "benchmark_value_eur",
        "benchmark_price_eur",
        "external_flow_eur",
        "weighted_external_flow_eur",
        "benchmark_flow_eur",
        "net_capital_invested_eur",
    ]

    for column in numeric_columns:
        history[column] = pd.to_numeric(
            history[column],
            errors="coerce",
        )

    flow_columns = [
        "external_flow_eur",
        "weighted_external_flow_eur",
        "benchmark_flow_eur",
    ]

    history[flow_columns] = (
        history[flow_columns]
        .fillna(0.0)
    )

    history[
        "previous_portfolio_value_eur"
    ] = history[
        "portfolio_value_eur"
    ].shift(1)

    history[
        "previous_benchmark_value_eur"
    ] = history[
        "benchmark_value_eur"
    ].shift(1)

    history[
        "previous_benchmark_price_eur"
    ] = history[
        "benchmark_price_eur"
    ].shift(1)

    # ========================================================
    # PORTFOLIO DAILY RETURN
    # ========================================================
    # Daily Modified Dietz approximation:
    #
    #     ending - beginning - net external flow
    # r = ----------------------------------------
    #     beginning + weighted external flow
    #
    # Trades within the account do not appear here because a
    # buy/sell only changes the split between cash and holdings.
    # ========================================================

    beginning = history[
        "previous_portfolio_value_eur"
    ]

    ending = history[
        "portfolio_value_eur"
    ]

    external_flow = history[
        "external_flow_eur"
    ]

    weighted_flow = history[
        "weighted_external_flow_eur"
    ]

    denominator = (
        beginning
        + weighted_flow
    )

    numerator = (
        ending
        - beginning
        - external_flow
    )

    history[
        "portfolio_daily_return"
    ] = np.nan

    valid_portfolio_return = (
        beginning.notna()
        & ending.notna()
        & (ending >= -0.01)
        & (denominator > 1e-8)
    )

    history.loc[
        valid_portfolio_return,
        "portfolio_daily_return",
    ] = (
        numerator.loc[
            valid_portfolio_return
        ]
        / denominator.loc[
            valid_portfolio_return
        ]
    )

    # In an unleveraged Invest/ISA account, a daily return less
    # than -100% is not economically possible. Treat it as a
    # reconstruction/timing failure rather than letting it poison
    # every downstream metric.
    impossible_loss = (
        history["portfolio_daily_return"]
        < -1.000001
    )

    history.loc[
        impossible_loss,
        "portfolio_daily_return",
    ] = np.nan

    history[
        "portfolio_return_valid"
    ] = history[
        "portfolio_daily_return"
    ].notna()

    # ========================================================
    # BENCHMARK DAILY RETURN
    # ========================================================
    # TWR for the S&P benchmark is simply the return of the EUR
    # benchmark price series. External flows are only needed to
    # construct benchmark VALUE and benchmark MWR, not benchmark
    # TWR itself.
    # ========================================================

    benchmark_previous_price = history[
        "previous_benchmark_price_eur"
    ]

    history[
        "benchmark_daily_return"
    ] = np.nan

    benchmark_valid = (
        benchmark_previous_price.notna()
        & history["benchmark_price_eur"].notna()
        & (benchmark_previous_price > 0)
        & (history["benchmark_price_eur"] > 0)
    )

    history.loc[
        benchmark_valid,
        "benchmark_daily_return",
    ] = (
        history.loc[
            benchmark_valid,
            "benchmark_price_eur",
        ]
        / benchmark_previous_price.loc[
            benchmark_valid
        ]
        - 1.0
    )

    # ========================================================
    # CUMULATIVE TWR
    # ========================================================
    # Undefined days (first day, zero-capital gaps, impossible
    # reconstruction observations) are neutral for chaining, but
    # remain NaN in the raw daily-return series so risk statistics
    # can exclude them rather than treating them as genuine 0% days.
    # ========================================================

    portfolio_link_returns = (
        history["portfolio_daily_return"]
        .fillna(0.0)
    )

    benchmark_link_returns = (
        history["benchmark_daily_return"]
        .fillna(0.0)
    )

    history["portfolio_growth_index"] = (
        1.0
        + portfolio_link_returns
    ).cumprod()

    history["benchmark_growth_index"] = (
        1.0
        + benchmark_link_returns
    ).cumprod()

    history["portfolio_twr_pct"] = (
        history["portfolio_growth_index"]
        - 1.0
    ) * 100.0

    history["benchmark_twr_pct"] = (
        history["benchmark_growth_index"]
        - 1.0
    ) * 100.0

    history["relative_growth_index"] = (
        history["portfolio_growth_index"]
        / history["benchmark_growth_index"]
    )

    history["relative_return_pct"] = (
        history["relative_growth_index"]
        - 1.0
    ) * 100.0

    history["relative_return_pp"] = (
        history["portfolio_twr_pct"]
        - history["benchmark_twr_pct"]
    )

    # ========================================================
    # ACCOUNT PROFIT / SIMPLE RETURN
    # ========================================================

    history["simple_gain_eur"] = (
        history["portfolio_value_eur"]
        - history["net_capital_invested_eur"]
    )

    history["simple_return_pct"] = np.nan

    capital_valid = (
        history["net_capital_invested_eur"]
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
        / history.loc[
            capital_valid,
            "net_capital_invested_eur",
        ]
        * 100.0
    )

    # ========================================================
    # DRAWDOWN
    # ========================================================

    history["portfolio_peak_index"] = (
        history["portfolio_growth_index"]
        .cummax()
    )

    history["benchmark_peak_index"] = (
        history["benchmark_growth_index"]
        .cummax()
    )

    history["portfolio_drawdown_pct"] = (
        history["portfolio_growth_index"]
        / history["portfolio_peak_index"]
        - 1.0
    ) * 100.0

    history["benchmark_drawdown_pct"] = (
        history["benchmark_growth_index"]
        / history["benchmark_peak_index"]
        - 1.0
    ) * 100.0

    latest = history.iloc[-1]

    valid_portfolio_daily = (
        history["portfolio_daily_return"]
        .replace(
            [np.inf, -np.inf],
            np.nan,
        )
        .dropna()
    )

    summary = {
        "portfolio_value_eur": float(
            latest["portfolio_value_eur"]
        ),
        "benchmark_value_eur": float(
            latest["benchmark_value_eur"]
        ),
        "net_capital_invested_eur": float(
            latest[
                "net_capital_invested_eur"
            ]
        ),
        "simple_gain_eur": float(
            latest["simple_gain_eur"]
        ),
        "simple_return_pct": (
            float(
                latest["simple_return_pct"]
            )
            if pd.notna(
                latest["simple_return_pct"]
            )
            else np.nan
        ),
        "portfolio_twr_pct": float(
            latest["portfolio_twr_pct"]
        ),
        "benchmark_twr_pct": float(
            latest["benchmark_twr_pct"]
        ),
        "relative_return_pct": float(
            latest["relative_return_pct"]
        ),
        "relative_return_pp": float(
            latest["relative_return_pp"]
        ),
        "portfolio_max_drawdown_pct": float(
            history[
                "portfolio_drawdown_pct"
            ].min()
        ),
        "benchmark_max_drawdown_pct": float(
            history[
                "benchmark_drawdown_pct"
            ].min()
        ),
        "peak_net_capital_eur": float(
            history[
                "net_capital_invested_eur"
            ].max()
        ),
        "worst_portfolio_day_pct": (
            float(
                valid_portfolio_daily.min()
                * 100.0
            )
            if not valid_portfolio_daily.empty
            else np.nan
        ),
        "best_portfolio_day_pct": (
            float(
                valid_portfolio_daily.max()
                * 100.0
            )
            if not valid_portfolio_daily.empty
            else np.nan
        ),
        "invalid_return_observations": int(
            (~history[
                "portfolio_return_valid"
            ]).sum()
        ),
    }

    return history, summary
