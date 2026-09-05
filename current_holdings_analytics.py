import numpy as np
import pandas as pd

from trading212 import get_positions
from market_data import get_all_price_history
from fx_data import get_fx_history
from performance_metrics import get_performance_metrics


TRADING_DAYS = 252

PERIODS = {
    "1Y": pd.DateOffset(years=1),
    "3M": pd.DateOffset(months=3),
    "1M": pd.DateOffset(months=1),
}


def _safe_number(value):
    try:
        value = float(value)

        if np.isfinite(value):
            return value

    except (TypeError, ValueError):
        pass

    return np.nan


def _load_fx_history(
    currency,
    start_date=None,
    force_refresh=False,
):
    """
    Return historical conversion rates from one unit of the
    supplied currency into EUR.

    EUR itself is handled separately and does not require an
    external FX series.
    """

    currency = str(currency).upper()

    if currency == "EUR":
        return None

    # Keep this compatible with the existing fx_data interface
    # even if optional arguments differ.
    try:
        fx = get_fx_history(
            currency,
            start_date=start_date,
            force_refresh=force_refresh,
        )

    except TypeError:

        try:
            fx = get_fx_history(
                currency,
                start_date=start_date,
            )

        except TypeError:

            fx = get_fx_history(
                currency
            )

    if fx is None or len(fx) == 0:
        raise ValueError(
            f"No FX history available for {currency}."
        )

    fx = fx.copy()

    if "date" not in fx.columns:
        raise ValueError(
            f"FX history for {currency} has no date column."
        )

    fx["date"] = pd.to_datetime(
        fx["date"],
        errors="coerce",
    )

    fx = (
        fx
        .dropna(subset=["date"])
        .sort_values("date")
        .drop_duplicates(
            subset=["date"],
            keep="last",
        )
    )

    # Preferred explicit conversion columns.
    if "currency_to_eur" in fx.columns:

        fx["fx_to_eur"] = pd.to_numeric(
            fx["currency_to_eur"],
            errors="coerce",
        )

    elif "rate_to_eur" in fx.columns:

        fx["fx_to_eur"] = pd.to_numeric(
            fx["rate_to_eur"],
            errors="coerce",
        )

    elif "to_eur" in fx.columns:

        fx["fx_to_eur"] = pd.to_numeric(
            fx["to_eur"],
            errors="coerce",
        )

    elif "eur_to_currency" in fx.columns:

        eur_to_currency = pd.to_numeric(
            fx["eur_to_currency"],
            errors="coerce",
        )

        fx["fx_to_eur"] = (
            1.0
            / eur_to_currency
        )

    else:

        raise ValueError(
            f"Unable to identify the FX conversion column "
            f"for {currency}. Columns: {fx.columns.tolist()}"
        )

    fx = fx[
        [
            "date",
            "fx_to_eur",
        ]
    ].dropna()

    return fx


def _prepare_price_history(
    positions,
    force_refresh=False,
):
    """
    Load historical market prices for today's holdings and
    convert every instrument into EUR.
    """

    tickers = (
        positions["ticker"]
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    )

    try:
        prices = get_all_price_history(
            tickers,
            force_refresh=force_refresh,
        )

    except TypeError:

        prices = get_all_price_history(
            tickers
        )

    if prices is None or len(prices) == 0:
        raise ValueError(
            "No historical price data was returned."
        )

    prices = prices.copy()

    prices["date"] = pd.to_datetime(
        prices["date"],
        errors="coerce",
    )

    prices["close"] = pd.to_numeric(
        prices["close"],
        errors="coerce",
    )

    prices = prices.dropna(
        subset=[
            "date",
            "trading212_ticker",
            "close",
        ]
    )

    prices = prices.sort_values(
        [
            "trading212_ticker",
            "date",
        ]
    )

    converted = []

    for ticker, ticker_data in prices.groupby(
        "trading212_ticker"
    ):

        ticker_data = ticker_data.copy()

        currency = str(
            ticker_data[
                "currency"
            ].dropna().iloc[-1]
        ).upper()

        if currency == "EUR":

            ticker_data[
                "fx_to_eur"
            ] = 1.0

        else:

            fx = _load_fx_history(
                currency,
                start_date=(
                    ticker_data[
                        "date"
                    ].min()
                ),
                force_refresh=force_refresh,
            )

            ticker_data = (
                pd.merge_asof(
                    ticker_data.sort_values(
                        "date"
                    ),
                    fx.sort_values(
                        "date"
                    ),
                    on="date",
                    direction="backward",
                )
            )

            ticker_data[
                "fx_to_eur"
            ] = (
                ticker_data[
                    "fx_to_eur"
                ]
                .ffill()
                .bfill()
            )

        ticker_data[
            "close_eur"
        ] = (
            ticker_data["close"]
            * ticker_data[
                "fx_to_eur"
            ]
        )

        ticker_data[
            "daily_return_eur"
        ] = (
            ticker_data[
                "close_eur"
            ]
            .pct_change(
                fill_method=None
            )
        )

        converted.append(
            ticker_data
        )

    return pd.concat(
        converted,
        ignore_index=True,
    )


def _get_current_weights():
    """
    Read the actual live Trading 212 holdings and calculate
    today's portfolio weights from current EUR market value.
    """

    positions = get_positions()

    if positions is None or len(positions) == 0:
        raise ValueError(
            "Trading 212 returned no current positions."
        )

    positions = positions.copy()

    positions[
        "current_value"
    ] = pd.to_numeric(
        positions[
            "current_value"
        ],
        errors="coerce",
    )

    positions = positions[
        positions[
            "current_value"
        ] > 0
    ].copy()

    total_value = (
        positions[
            "current_value"
        ].sum()
    )

    if total_value <= 0:
        raise ValueError(
            "Current holdings have no positive market value."
        )

    positions[
        "weight"
    ] = (
        positions[
            "current_value"
        ]
        / total_value
    )

    return positions


def _get_benchmark_returns():
    """
    Reuse the benchmark series already used by the portfolio
    engine so all analytics remain directly comparable.
    """

    history, _ = get_performance_metrics()

    history = history.copy()

    history["date"] = pd.to_datetime(
        history["date"],
        errors="coerce",
    )

    benchmark = history[
        [
            "date",
            "benchmark_daily_return",
        ]
    ].copy()

    benchmark[
        "benchmark_daily_return"
    ] = pd.to_numeric(
        benchmark[
            "benchmark_daily_return"
        ],
        errors="coerce",
    )

    return (
        benchmark
        .dropna(subset=["date"])
        .sort_values("date")
        .drop_duplicates(
            subset=["date"],
            keep="last",
        )
    )


def _build_current_portfolio_returns(
    positions,
    prices,
):
    """
    Construct the historical return series of today's portfolio.

    Today's live weights are kept constant throughout the
    historical simulation. This lets us ask:

    "How would the portfolio I own right now have behaved over
    the previous month, three months or year?"
    """

    returns = (
        prices.pivot_table(
            index="date",
            columns="trading212_ticker",
            values="daily_return_eur",
            aggfunc="last",
        )
        .sort_index()
    )

    weights = (
        positions
        .set_index("ticker")[
            "weight"
        ]
    )

    available_tickers = [
        ticker
        for ticker in weights.index
        if ticker in returns.columns
    ]

    if not available_tickers:
        raise ValueError(
            "None of the current holdings have price history."
        )

    returns = returns[
        available_tickers
    ]

    weights = weights[
        available_tickers
    ]

    # Renormalise in case one current instrument could not be
    # represented in the historical market data.
    weights = (
        weights
        / weights.sum()
    )

    # Require all current holdings to have a return on the day.
    # This keeps portfolio beta/risk mathematically consistent
    # with the individual contribution calculations.
    valid = returns.dropna(
        how="any"
    )

    portfolio_returns = (
        valid
        .mul(
            weights,
            axis=1,
        )
        .sum(axis=1)
    )

    result = pd.DataFrame(
        {
            "date":
                portfolio_returns.index,

            "current_portfolio_return":
                portfolio_returns.values,
        }
    )

    return (
        result,
        valid,
        weights,
    )


def _calculate_drawdown(
    returns,
):
    returns = (
        pd.Series(
            returns,
            dtype=float,
        )
        .dropna()
    )

    if len(returns) == 0:
        return (
            np.nan,
            0,
        )

    growth = (
        1.0
        + returns
    ).cumprod()

    wealth = pd.concat(
        [
            pd.Series(
                [1.0]
            ),
            growth.reset_index(
                drop=True
            ),
        ],
        ignore_index=True,
    )

    running_peak = (
        wealth.cummax()
    )

    drawdown = (
        wealth
        / running_peak
        - 1.0
    )

    max_drawdown = (
        drawdown.min()
        * 100
    )

    current_duration = 0
    longest_duration = 0

    for value in drawdown.iloc[1:]:

        if value < 0:

            current_duration += 1

            longest_duration = max(
                longest_duration,
                current_duration,
            )

        else:

            current_duration = 0

    return (
        float(max_drawdown),
        int(longest_duration),
    )


def _calculate_basic_metrics(
    portfolio_returns,
    benchmark_returns,
    ending_value,
    risk_free_rate=0.0,
    var_confidence=0.95,
):
    data = pd.concat(
        [
            portfolio_returns.rename(
                "portfolio"
            ),
            benchmark_returns.rename(
                "benchmark"
            ),
        ],
        axis=1,
    ).dropna()

    if len(data) < 2:
        return {}

    p = data["portfolio"]
    b = data["benchmark"]

    portfolio_growth = float(
        (1.0 + p).prod()
    )

    benchmark_growth = float(
        (1.0 + b).prod()
    )

    portfolio_return = (
        portfolio_growth
        - 1.0
    )

    benchmark_return = (
        benchmark_growth
        - 1.0
    )

    volatility = (
        p.std(ddof=1)
        * np.sqrt(
            TRADING_DAYS
        )
    )

    benchmark_variance = (
        b.var(ddof=1)
    )

    beta = (
        p.cov(b)
        / benchmark_variance
        if benchmark_variance > 0
        else np.nan
    )

    correlation = p.corr(b)

    daily_rf = (
        (1.0 + risk_free_rate)
        ** (
            1.0
            / TRADING_DAYS
        )
        - 1.0
    )

    excess = (
        p
        - daily_rf
    )

    excess_std = excess.std(
        ddof=1
    )

    sharpe = (
        excess.mean()
        / excess_std
        * np.sqrt(
            TRADING_DAYS
        )
        if excess_std > 0
        else np.nan
    )

    downside = excess[
        excess < 0
    ]

    if len(downside) > 0:

        downside_deviation = np.sqrt(
            (
                downside
                ** 2
            ).mean()
        )

        sortino = (
            excess.mean()
            / downside_deviation
            * np.sqrt(
                TRADING_DAYS
            )
            if downside_deviation > 0
            else np.nan
        )

    else:

        sortino = np.nan

    var = (
        -np.quantile(
            p,
            1.0
            - var_confidence,
        )
    )

    (
        max_drawdown,
        drawdown_duration,
    ) = _calculate_drawdown(
        p
    )

    return {
        "observations":
            int(len(data)),

        "current_portfolio_return_pct":
            float(
                portfolio_return
                * 100
            ),

        "benchmark_return_pct":
            float(
                benchmark_return
                * 100
            ),

        "relative_return_pp":
            float(
                (
                    portfolio_return
                    - benchmark_return
                )
                * 100
            ),

        "annualised_volatility_pct":
            float(
                volatility
                * 100
            ),

        "beta":
            _safe_number(
                beta
            ),

        "correlation":
            _safe_number(
                correlation
            ),

        "sharpe_ratio":
            _safe_number(
                sharpe
            ),

        "sortino_ratio":
            _safe_number(
                sortino
            ),

        "max_drawdown_pct":
            float(
                max_drawdown
            ),

        "drawdown_duration_days":
            int(
                drawdown_duration
            ),

        "historical_var_pct":
            float(
                var
                * 100
            ),

        "historical_var_eur":
            float(
                var
                * ending_value
            ),

        "best_day_pct":
            float(
                p.max()
                * 100
            ),

        "worst_day_pct":
            float(
                p.min()
                * 100
            ),
    }


def _individual_holding_metrics(
    period_returns,
    benchmark_returns,
    weights,
):
    """
    Calculate beta, volatility and risk contribution for each
    position currently held.
    """

    benchmark_returns = (
        benchmark_returns
        .reindex(
            period_returns.index
        )
    )

    aligned = (
        period_returns
        .copy()
    )

    aligned[
        "__benchmark__"
    ] = benchmark_returns

    aligned = aligned.dropna()

    if len(aligned) < 2:
        return pd.DataFrame()

    stock_returns = aligned.drop(
        columns=[
            "__benchmark__"
        ]
    )

    benchmark = aligned[
        "__benchmark__"
    ]

    weights = weights.reindex(
        stock_returns.columns
    )

    weights = (
        weights
        / weights.sum()
    )

    portfolio_returns = (
        stock_returns
        .mul(
            weights,
            axis=1,
        )
        .sum(axis=1)
    )

    covariance_matrix = (
        stock_returns.cov()
    )

    weight_vector = weights.values

    portfolio_variance = float(
        weight_vector.T
        @ covariance_matrix.values
        @ weight_vector
    )

    if portfolio_variance > 0:

        marginal_component = (
            covariance_matrix.values
            @ weight_vector
        )

        variance_contribution = (
            weight_vector
            * marginal_component
            / portfolio_variance
        )

    else:

        variance_contribution = (
            np.full(
                len(weights),
                np.nan,
            )
        )

    benchmark_variance = (
        benchmark.var(ddof=1)
    )

    records = []

    for index, ticker in enumerate(
        stock_returns.columns
    ):

        r = stock_returns[
            ticker
        ]

        beta = (
            r.cov(
                benchmark
            )
            / benchmark_variance
            if benchmark_variance > 0
            else np.nan
        )

        volatility = (
            r.std(ddof=1)
            * np.sqrt(
                TRADING_DAYS
            )
        )

        correlation = (
            r.corr(
                benchmark
            )
        )

        total_return = (
            (1.0 + r).prod()
            - 1.0
        )

        beta_contribution = (
            weights[
                ticker
            ]
            * beta
        )

        records.append(
            {
                "ticker":
                    ticker,

                "weight_pct":
                    float(
                        weights[
                            ticker
                        ]
                        * 100
                    ),

                "return_pct":
                    float(
                        total_return
                        * 100
                    ),

                "beta":
                    _safe_number(
                        beta
                    ),

                "beta_contribution":
                    _safe_number(
                        beta_contribution
                    ),

                "annualised_volatility_pct":
                    float(
                        volatility
                        * 100
                    ),

                "correlation":
                    _safe_number(
                        correlation
                    ),

                "variance_contribution_pct":
                    float(
                        variance_contribution[
                            index
                        ]
                        * 100
                    ),
            }
        )

    return pd.DataFrame(
        records
    )


def get_current_holdings_analytics(
    period="1M",
    force_refresh=False,
):
    """
    Analyse today's exact portfolio weights over a historical
    1M, 3M or 1Y window.
    """

    period = period.upper()

    if period not in PERIODS:
        raise ValueError(
            "Period must be one of: 1M, 3M, 1Y."
        )

    positions = (
        _get_current_weights()
    )

    prices = (
        _prepare_price_history(
            positions,
            force_refresh=force_refresh,
        )
    )

    (
        portfolio_history,
        stock_returns,
        weights,
    ) = (
        _build_current_portfolio_returns(
            positions,
            prices,
        )
    )

    benchmark = (
        _get_benchmark_returns()
        .set_index("date")[
            "benchmark_daily_return"
        ]
    )

    portfolio_history = (
        portfolio_history
        .set_index("date")
        .sort_index()
    )

    last_date = (
        portfolio_history.index.max()
    )

    cutoff = (
        last_date
        - PERIODS[
            period
        ]
    )

    period_portfolio = (
        portfolio_history.loc[
            portfolio_history.index
            >= cutoff
        ][
            "current_portfolio_return"
        ]
    )

    period_stock_returns = (
        stock_returns.loc[
            stock_returns.index
            >= cutoff
        ]
    )

    period_benchmark = (
        benchmark.reindex(
            period_portfolio.index
        )
    )

    total_current_value = float(
        positions[
            "current_value"
        ].sum()
    )

    summary = (
        _calculate_basic_metrics(
            period_portfolio,
            period_benchmark,
            total_current_value,
        )
    )

    summary.update(
        {
            "period":
                period,

            "first_date":
                period_portfolio.index.min(),

            "last_date":
                period_portfolio.index.max(),

            "current_holdings_value_eur":
                total_current_value,

            "holding_count":
                int(
                    len(
                        positions
                    )
                ),
        }
    )

    holding_metrics = (
        _individual_holding_metrics(
            period_stock_returns,
            benchmark,
            weights,
        )
    )

    metadata = positions[
        [
            "ticker",
            "display_ticker",
            "company",
            "current_value",
            "unrealised_pnl",
            "weight",
        ]
    ].copy()

    holding_metrics = (
        holding_metrics.merge(
            metadata,
            on="ticker",
            how="left",
        )
    )

    holding_metrics[
        "current_value_eur"
    ] = holding_metrics[
        "current_value"
    ]

    holding_metrics[
        "current_weight_pct"
    ] = (
        holding_metrics[
            "weight"
        ]
        * 100
    )

    holding_metrics = (
        holding_metrics[
            [
                "ticker",
                "display_ticker",
                "company",
                "current_value_eur",
                "current_weight_pct",
                "return_pct",
                "beta",
                "beta_contribution",
                "annualised_volatility_pct",
                "correlation",
                "variance_contribution_pct",
                "unrealised_pnl",
            ]
        ]
        .sort_values(
            "current_value_eur",
            ascending=False,
        )
        .reset_index(
            drop=True
        )
    )

    return (
        summary,
        holding_metrics,
    )


def get_all_current_holdings_analytics(
    force_refresh=False,
):
    """
    Produce portfolio-level and holding-level statistics for
    1M, 3M and 1Y using today's portfolio weights.
    """

    summaries = []

    holdings_by_period = {}

    for period in [
        "1M",
        "3M",
        "1Y",
    ]:

        (
            summary,
            holdings,
        ) = (
            get_current_holdings_analytics(
                period=period,
                force_refresh=force_refresh,
            )
        )

        summaries.append(
            summary
        )

        holdings_by_period[
            period
        ] = holdings

    return (
        pd.DataFrame(
            summaries
        ),
        holdings_by_period,
    )