import numpy as np
import pandas as pd

from performance_metrics import get_performance_metrics


TRADING_DAYS = 252

PERIODS = {
    "FULL": None,
    "1Y": pd.DateOffset(years=1),
    "3M": pd.DateOffset(months=3),
    "1M": pd.DateOffset(months=1),
}


def _prepare_history(force_refresh=False):
    history, _ = get_performance_metrics(
        force_refresh=force_refresh,
    )

    history = history.copy()

    history["date"] = pd.to_datetime(
        history["date"],
        errors="coerce",
    )

    history = (
        history
        .dropna(subset=["date"])
        .sort_values("date")
        .reset_index(drop=True)
    )

    return history


def _get_period_slice(history, period):
    """
    Return the rows belonging to the selected trailing period,
    plus the portfolio/benchmark value immediately before the
    period began.

    The previous observation is important because the first
    day's return inside the period must still be included.
    """

    period = period.upper()

    if period not in PERIODS:
        raise ValueError(
            f"Unknown period '{period}'. "
            f"Use one of: {list(PERIODS.keys())}"
        )

    if history.empty:
        raise ValueError(
            "Performance history is empty."
        )

    last_date = history.iloc[-1]["date"]

    offset = PERIODS[period]

    if offset is None:
        start_index = 0

    else:
        cutoff = last_date - offset

        eligible = history.index[
            history["date"] >= cutoff
        ]

        if len(eligible) == 0:
            start_index = 0
        else:
            start_index = int(
                eligible[0]
            )

    period_history = (
        history.iloc[start_index:]
        .copy()
        .reset_index(drop=True)
    )

    if start_index > 0:
        previous_row = (
            history.iloc[
                start_index - 1
            ]
        )
    else:
        previous_row = None

    return (
        period_history,
        previous_row,
    )


def _calculate_drawdown(
    growth_values,
):
    """
    Calculate period-local drawdown.

    An implicit starting index of 1.0 is included so a loss on
    the first day of the selected period is measured correctly.
    """

    values = np.asarray(
        growth_values,
        dtype=float,
    )

    if len(values) == 0:
        return (
            np.array([]),
            np.nan,
            0,
        )

    running_peak = (
        np.maximum.accumulate(
            np.concatenate(
                [
                    [1.0],
                    values,
                ]
            )
        )[1:]
    )

    drawdown = (
        values
        / running_peak
        - 1.0
    )

    max_drawdown = float(
        np.min(drawdown)
        * 100
    )

    current_duration = 0
    max_duration = 0

    for value in drawdown:

        if value < 0:
            current_duration += 1

            max_duration = max(
                max_duration,
                current_duration,
            )

        else:
            current_duration = 0

    return (
        drawdown,
        max_drawdown,
        max_duration,
    )


def get_period_analytics(
    period="FULL",
    force_refresh=False,
    risk_free_rate=0.0,
    var_confidence=0.95,
):
    """
    Calculate performance and risk statistics for one period.

    Supported periods:
        FULL
        1Y
        3M
        1M
    """

    history = _prepare_history(
        force_refresh=force_refresh,
    )

    (
        period_history,
        previous_row,
    ) = _get_period_slice(
        history,
        period,
    )

    if period_history.empty:
        raise ValueError(
            "No data is available for "
            f"period {period}."
        )

    first_date = (
        period_history.iloc[0][
            "date"
        ]
    )

    last_date = (
        period_history.iloc[-1][
            "date"
        ]
    )

    if previous_row is not None:

        starting_portfolio_value = float(
            previous_row[
                "portfolio_value_eur"
            ]
        )

        starting_benchmark_value = float(
            previous_row[
                "benchmark_value_eur"
            ]
        )

        starting_portfolio_growth = float(
            previous_row[
                "portfolio_growth_index"
            ]
        )

        starting_benchmark_growth = float(
            previous_row[
                "benchmark_growth_index"
            ]
        )

    else:

        starting_portfolio_value = 0.0
        starting_benchmark_value = 0.0

        starting_portfolio_growth = 1.0
        starting_benchmark_growth = 1.0

    ending_portfolio_value = float(
        period_history.iloc[-1][
            "portfolio_value_eur"
        ]
    )

    ending_benchmark_value = float(
        period_history.iloc[-1][
            "benchmark_value_eur"
        ]
    )

    ending_portfolio_growth = float(
        period_history.iloc[-1][
            "portfolio_growth_index"
        ]
    )

    ending_benchmark_growth = float(
        period_history.iloc[-1][
            "benchmark_growth_index"
        ]
    )

    # Cash-flow-adjusted period performance.
    portfolio_period_growth = (
        ending_portfolio_growth
        / starting_portfolio_growth
    )

    benchmark_period_growth = (
        ending_benchmark_growth
        / starting_benchmark_growth
    )

    portfolio_twr = (
        portfolio_period_growth
        - 1.0
    )

    benchmark_twr = (
        benchmark_period_growth
        - 1.0
    )

    relative_return = (
        portfolio_period_growth
        / benchmark_period_growth
        - 1.0
    )

    relative_pp = (
        portfolio_twr
        - benchmark_twr
    )

    # Actual € investment profit during the selected period.
    # Deposits are positive external flows and withdrawals are
    # negative, so removing them isolates investment performance.
    external_flows = float(
        period_history[
            "external_flow_eur"
        ].sum()
    )

    benchmark_flows = float(
        period_history[
            "benchmark_flow_eur"
        ].sum()
    )

    portfolio_profit_eur = (
        ending_portfolio_value
        - starting_portfolio_value
        - external_flows
    )

    benchmark_profit_eur = (
        ending_benchmark_value
        - starting_benchmark_value
        - benchmark_flows
    )

    # --------------------------------------------------------
    # Risk statistics use trading weekdays only.
    # --------------------------------------------------------

    market_history = (
        period_history[
            period_history[
                "date"
            ].dt.weekday < 5
        ]
        .copy()
    )

    aligned = (
        market_history[
            [
                "portfolio_daily_return",
                "benchmark_daily_return",
            ]
        ]
        .replace(
            [np.inf, -np.inf],
            np.nan,
        )
        .dropna()
    )

    observations = len(
        aligned
    )

    if observations >= 2:

        p = aligned[
            "portfolio_daily_return"
        ]

        b = aligned[
            "benchmark_daily_return"
        ]

        portfolio_volatility = (
            p.std(ddof=1)
            * np.sqrt(
                TRADING_DAYS
            )
        )

        benchmark_volatility = (
            b.std(ddof=1)
            * np.sqrt(
                TRADING_DAYS
            )
        )

        benchmark_variance = (
            b.var(ddof=1)
        )

        if benchmark_variance > 0:
            beta = (
                p.cov(b)
                / benchmark_variance
            )
        else:
            beta = np.nan

        correlation = p.corr(b)

        daily_risk_free = (
            (1 + risk_free_rate)
            ** (
                1 / TRADING_DAYS
            )
            - 1
        )

        excess_returns = (
            p
            - daily_risk_free
        )

        excess_std = (
            excess_returns.std(
                ddof=1
            )
        )

        if excess_std > 0:

            sharpe = (
                excess_returns.mean()
                / excess_std
                * np.sqrt(
                    TRADING_DAYS
                )
            )

        else:
            sharpe = np.nan

        downside_returns = (
            excess_returns[
                excess_returns < 0
            ]
        )

        if len(
            downside_returns
        ) > 0:

            downside_deviation = (
                np.sqrt(
                    (
                        downside_returns
                        ** 2
                    ).mean()
                )
            )

        else:
            downside_deviation = (
                np.nan
            )

        if (
            np.isfinite(
                downside_deviation
            )
            and downside_deviation > 0
        ):

            sortino = (
                excess_returns.mean()
                / downside_deviation
                * np.sqrt(
                    TRADING_DAYS
                )
            )

        else:
            sortino = np.nan

        historical_var = (
            -np.quantile(
                p,
                1
                - var_confidence,
            )
        )

        historical_var_eur = (
            ending_portfolio_value
            * historical_var
        )

        best_day = float(
            p.max()
            * 100
        )

        worst_day = float(
            p.min()
            * 100
        )

    else:

        portfolio_volatility = np.nan
        benchmark_volatility = np.nan
        beta = np.nan
        correlation = np.nan
        sharpe = np.nan
        sortino = np.nan
        historical_var = np.nan
        historical_var_eur = np.nan
        best_day = np.nan
        worst_day = np.nan

    # --------------------------------------------------------
    # Period-local drawdown
    # --------------------------------------------------------

    portfolio_growth_series = (
        period_history[
            "portfolio_growth_index"
        ]
        / starting_portfolio_growth
    )

    benchmark_growth_series = (
        period_history[
            "benchmark_growth_index"
        ]
        / starting_benchmark_growth
    )

    (
        portfolio_drawdown,
        max_drawdown,
        max_drawdown_duration,
    ) = _calculate_drawdown(
        portfolio_growth_series
    )

    (
        benchmark_drawdown,
        benchmark_max_drawdown,
        benchmark_drawdown_duration,
    ) = _calculate_drawdown(
        benchmark_growth_series
    )

    period_history[
        "period_portfolio_growth_index"
    ] = portfolio_growth_series

    period_history[
        "period_benchmark_growth_index"
    ] = benchmark_growth_series

    period_history[
        "period_portfolio_drawdown_pct"
    ] = (
        portfolio_drawdown
        * 100
    )

    period_history[
        "period_benchmark_drawdown_pct"
    ] = (
        benchmark_drawdown
        * 100
    )

    calendar_days = (
        last_date
        - first_date
    ).days

    elapsed_years = (
        calendar_days
        / 365.25
    )

    # CAGR is useful for periods around one year or longer.
    if (
        calendar_days >= 365
        and portfolio_period_growth > 0
    ):

        portfolio_cagr = (
            portfolio_period_growth
            ** (
                1 / elapsed_years
            )
            - 1
        )

        benchmark_cagr = (
            benchmark_period_growth
            ** (
                1 / elapsed_years
            )
            - 1
        )

    else:

        portfolio_cagr = np.nan
        benchmark_cagr = np.nan

    summary = {

        "period":
            period.upper(),

        "first_date":
            first_date,

        "last_date":
            last_date,

        "calendar_days":
            int(calendar_days),

        "trading_observations":
            int(observations),

        "starting_portfolio_value_eur":
            float(
                starting_portfolio_value
            ),

        "ending_portfolio_value_eur":
            float(
                ending_portfolio_value
            ),

        "portfolio_profit_eur":
            float(
                portfolio_profit_eur
            ),

        "external_flows_eur":
            float(
                external_flows
            ),

        "portfolio_twr_pct":
            float(
                portfolio_twr
                * 100
            ),

        "benchmark_twr_pct":
            float(
                benchmark_twr
                * 100
            ),

        "relative_return_pct":
            float(
                relative_return
                * 100
            ),

        "relative_return_pp":
            float(
                relative_pp
                * 100
            ),

        "portfolio_cagr_pct":
            (
                float(
                    portfolio_cagr
                    * 100
                )
                if np.isfinite(
                    portfolio_cagr
                )
                else np.nan
            ),

        "benchmark_cagr_pct":
            (
                float(
                    benchmark_cagr
                    * 100
                )
                if np.isfinite(
                    benchmark_cagr
                )
                else np.nan
            ),

        "annualised_volatility_pct":
            (
                float(
                    portfolio_volatility
                    * 100
                )
                if np.isfinite(
                    portfolio_volatility
                )
                else np.nan
            ),

        "benchmark_volatility_pct":
            (
                float(
                    benchmark_volatility
                    * 100
                )
                if np.isfinite(
                    benchmark_volatility
                )
                else np.nan
            ),

        "beta":
            (
                float(beta)
                if np.isfinite(beta)
                else np.nan
            ),

        "correlation":
            (
                float(
                    correlation
                )
                if np.isfinite(
                    correlation
                )
                else np.nan
            ),

        "sharpe_ratio":
            (
                float(sharpe)
                if np.isfinite(
                    sharpe
                )
                else np.nan
            ),

        "sortino_ratio":
            (
                float(sortino)
                if np.isfinite(
                    sortino
                )
                else np.nan
            ),

        "max_drawdown_pct":
            float(
                max_drawdown
            ),

        "max_drawdown_duration_days":
            int(
                max_drawdown_duration
            ),

        "benchmark_max_drawdown_pct":
            float(
                benchmark_max_drawdown
            ),

        "benchmark_drawdown_duration_days":
            int(
                benchmark_drawdown_duration
            ),

        "historical_var_pct":
            (
                float(
                    historical_var
                    * 100
                )
                if np.isfinite(
                    historical_var
                )
                else np.nan
            ),

        "historical_var_eur":
            (
                float(
                    historical_var_eur
                )
                if np.isfinite(
                    historical_var_eur
                )
                else np.nan
            ),

        "best_day_pct":
            float(
                best_day
            ),

        "worst_day_pct":
            float(
                worst_day
            ),
    }

    return (
        period_history,
        summary,
    )


def get_all_period_analytics(
    force_refresh=False,
):
    """
    Produce one summary table covering every dashboard period.
    """

    records = []

    for period in [
        "FULL",
        "1Y",
        "3M",
        "1M",
    ]:

        _, summary = (
            get_period_analytics(
                period=period,
                force_refresh=force_refresh,
            )
        )

        records.append(
            summary
        )

    return pd.DataFrame(
        records
    )