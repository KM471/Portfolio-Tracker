import numpy as np

from performance_metrics import get_performance_metrics


TRADING_DAYS = 252


def get_risk_metrics(
    force_refresh=False,
    risk_free_rate=0.0,
    var_confidence=0.95,
):

    history, _ = get_performance_metrics(
        force_refresh=force_refresh,
    )

    history = history.copy()

    # Risk statistics should use market weekdays rather than
    # artificial zero-return Saturday/Sunday observations.
    history["weekday"] = history["date"].dt.weekday

    market_history = history[
        history["weekday"] < 5
    ].copy()

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

    p = aligned[
        "portfolio_daily_return"
    ]

    b = aligned[
        "benchmark_daily_return"
    ]

    if len(aligned) < 2:
        raise ValueError(
            "Not enough return observations "
            "to calculate risk metrics."
        )

    # Annualised volatility
    volatility = (
        p.std(ddof=1)
        * np.sqrt(TRADING_DAYS)
    )

    benchmark_volatility = (
        b.std(ddof=1)
        * np.sqrt(TRADING_DAYS)
    )

    # Beta
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

    # Correlation
    correlation = (
        p.corr(b)
    )

    # Daily equivalent risk-free rate
    daily_risk_free = (
        (1 + risk_free_rate)
        ** (1 / TRADING_DAYS)
        - 1
    )

    excess_returns = (
        p
        - daily_risk_free
    )

    # Sharpe
    excess_std = (
        excess_returns.std(
            ddof=1
        )
    )

    if excess_std > 0:
        sharpe = (
            excess_returns.mean()
            / excess_std
            * np.sqrt(TRADING_DAYS)
        )
    else:
        sharpe = np.nan

    # Sortino
    downside_returns = (
        excess_returns[
            excess_returns < 0
        ]
    )

    if len(downside_returns) > 0:

        downside_deviation = (
            np.sqrt(
                (
                    downside_returns ** 2
                ).mean()
            )
        )

    else:
        downside_deviation = np.nan

    if (
        not np.isnan(
            downside_deviation
        )
        and downside_deviation > 0
    ):
        sortino = (
            excess_returns.mean()
            / downside_deviation
            * np.sqrt(TRADING_DAYS)
        )
    else:
        sortino = np.nan

    # Historical daily VaR
    percentile = (
        1
        - var_confidence
    )

    var_daily = (
        -np.quantile(
            p,
            percentile,
        )
    )

    current_value = float(
        history.iloc[-1][
            "portfolio_value_eur"
        ]
    )

    var_eur = (
        current_value
        * var_daily
    )

    # Maximum drawdown comes from the cash-flow-adjusted
    # TWR series, so withdrawals cannot create fake losses.
    drawdown = (
        history[
            "portfolio_drawdown_pct"
        ]
    )

    max_drawdown = float(
        drawdown.min()
    )

    # Drawdown duration remains in calendar days because this
    # measures how long an investor remained below the peak.
    underwater = (
        drawdown < 0
    )

    current_duration = 0
    max_duration = 0

    for value in underwater:

        if value:
            current_duration += 1

            max_duration = max(
                max_duration,
                current_duration,
            )

        else:
            current_duration = 0

    return {

        "observations":
            int(len(aligned)),

        "annualised_volatility_pct":
            float(
                volatility
                * 100
            ),

        "benchmark_volatility_pct":
            float(
                benchmark_volatility
                * 100
            ),

        "beta":
            float(beta),

        "correlation":
            float(correlation),

        "sharpe_ratio":
            float(sharpe),

        "sortino_ratio":
            float(sortino),

        "max_drawdown_pct":
            float(max_drawdown),

        "max_drawdown_duration_days":
            int(max_duration),

        "historical_var_pct":
            float(
                var_daily
                * 100
            ),

        "historical_var_eur":
            float(var_eur),
    }