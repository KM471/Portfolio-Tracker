import numpy as np
import pandas as pd
import streamlit as st
import altair as alt


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------

def _clean_history(history):
    data = history.copy()

    data["date"] = pd.to_datetime(
        data["date"],
        errors="coerce",
    )

    data = (
        data
        .dropna(subset=["date"])
        .sort_values("date")
        .reset_index(drop=True)
    )

    return data


def _clean_holdings(holdings):
    data = holdings.copy()

    numeric_columns = [
        column
        for column in data.columns
        if column not in [
            "ticker",
            "display_ticker",
            "company",
        ]
    ]

    for column in numeric_columns:
        data[column] = pd.to_numeric(
            data[column],
            errors="coerce",
        )

    return data


def _line_chart(
    data,
    y_columns,
    labels,
    title,
    y_title,
):
    chart_data = (
        data[
            ["date"] + y_columns
        ]
        .copy()
        .melt(
            id_vars="date",
            value_vars=y_columns,
            var_name="series",
            value_name="value",
        )
    )

    chart_data["series"] = (
        chart_data["series"]
        .map(labels)
    )

    chart = (
        alt.Chart(chart_data)
        .mark_line()
        .encode(
            x=alt.X(
                "date:T",
                title=None,
            ),
            y=alt.Y(
                "value:Q",
                title=y_title,
            ),
            color=alt.Color(
                "series:N",
                title=None,
            ),
            tooltip=[
                alt.Tooltip(
                    "date:T",
                    title="Date",
                ),
                alt.Tooltip(
                    "series:N",
                    title="Series",
                ),
                alt.Tooltip(
                    "value:Q",
                    title=y_title,
                    format=",.2f",
                ),
            ],
        )
        .properties(
            title=title,
            height=360,
        )
        .interactive()
    )

    st.altair_chart(
        chart,
        use_container_width=True,
    )


def _bar_chart(
    data,
    category_column,
    value_column,
    title,
    value_title,
):
    chart = (
        alt.Chart(data)
        .mark_bar()
        .encode(
            x=alt.X(
                f"{value_column}:Q",
                title=value_title,
            ),
            y=alt.Y(
                f"{category_column}:N",
                title=None,
                sort="-x",
            ),
            tooltip=[
                alt.Tooltip(
                    f"{category_column}:N",
                    title="Holding",
                ),
                alt.Tooltip(
                    f"{value_column}:Q",
                    title=value_title,
                    format=",.2f",
                ),
            ],
        )
        .properties(
            title=title,
            height=330,
        )
    )

    st.altair_chart(
        chart,
        use_container_width=True,
    )


# ------------------------------------------------------------
# Portfolio value and capital charts
# ------------------------------------------------------------

def render_value_charts(history):
    history = _clean_history(history)

    st.subheader("Portfolio Growth")

    view = st.radio(
        "Growth chart view",
        [
            "Percentage performance",
            "Euro values",
        ],
        horizontal=True,
        key="growth_chart_view",
    )

    if view == "Percentage performance":

        data = history.copy()

        data["portfolio_return_pct"] = (
            data["portfolio_growth_index"]
            - 1
        ) * 100

        data["benchmark_return_pct"] = (
            data["benchmark_growth_index"]
            - 1
        ) * 100

        _line_chart(
            data,
            [
                "portfolio_return_pct",
                "benchmark_return_pct",
            ],
            {
                "portfolio_return_pct":
                    "Portfolio",
                "benchmark_return_pct":
                    "S&P 500",
            },
            "Portfolio vs S&P 500",
            "Return %",
        )

    else:

        _line_chart(
            history,
            [
                "portfolio_value_eur",
                "benchmark_value_eur",
                "net_capital_invested_eur",
            ],
            {
                "portfolio_value_eur":
                    "Portfolio value",
                "benchmark_value_eur":
                    "S&P 500 equivalent",
                "net_capital_invested_eur":
                    "Net capital invested",
            },
            "Portfolio Value vs Capital Invested",
            "EUR",
        )


    st.caption(
        "The benchmark mirrors your portfolio cash flows, "
        "allowing performance to be compared fairly even when "
        "you add or withdraw capital."
    )


# ------------------------------------------------------------
# Capital history
# ------------------------------------------------------------

def render_capital_chart(history):
    history = _clean_history(history)

    st.subheader("Capital Invested")

    _line_chart(
        history,
        [
            "net_capital_invested_eur",
        ],
        {
            "net_capital_invested_eur":
                "Net capital invested",
        },
        "Net Capital Invested Over Time",
        "EUR",
    )

    peak_capital = (
        history[
            "net_capital_invested_eur"
        ]
        .max()
    )

    current_capital = (
        history[
            "net_capital_invested_eur"
        ]
        .iloc[-1]
    )

    withdrawn_from_peak = (
        peak_capital
        - current_capital
    )

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "Peak capital",
        f"€{peak_capital:,.2f}",
    )

    col2.metric(
        "Current net capital",
        f"€{current_capital:,.2f}",
    )

    col3.metric(
        "Capital removed since peak",
        f"€{withdrawn_from_peak:,.2f}",
    )


# ------------------------------------------------------------
# Profit chart
# ------------------------------------------------------------

def render_profit_chart(history):
    history = _clean_history(history)

    st.subheader("Profit History")

    _line_chart(
        history,
        [
            "simple_gain_eur",
        ],
        {
            "simple_gain_eur":
                "Investment profit",
        },
        "Investment Profit Over Time",
        "EUR",
    )


# ------------------------------------------------------------
# Drawdown chart
# ------------------------------------------------------------

def render_drawdown_chart(history):
    history = _clean_history(history)

    st.subheader("Drawdowns")

    _line_chart(
        history,
        [
            "portfolio_drawdown_pct",
            "benchmark_drawdown_pct",
        ],
        {
            "portfolio_drawdown_pct":
                "Portfolio",
            "benchmark_drawdown_pct":
                "S&P 500",
        },
        "Portfolio vs S&P 500 Drawdown",
        "Drawdown %",
    )


# ------------------------------------------------------------
# Rolling risk
# ------------------------------------------------------------

def _rolling_risk(history, window):
    data = _clean_history(history)

    portfolio_return = pd.to_numeric(
        data["portfolio_daily_return"],
        errors="coerce",
    )

    benchmark_return = pd.to_numeric(
        data["benchmark_daily_return"],
        errors="coerce",
    )

    data["rolling_volatility_pct"] = (
        portfolio_return
        .rolling(window)
        .std()
        * np.sqrt(252)
        * 100
    )

    benchmark_variance = (
        benchmark_return
        .rolling(window)
        .var()
    )

    covariance = (
        portfolio_return
        .rolling(window)
        .cov(
            benchmark_return
        )
    )

    data["rolling_beta"] = (
        covariance
        / benchmark_variance
    )

    data["rolling_correlation"] = (
        portfolio_return
        .rolling(window)
        .corr(
            benchmark_return
        )
    )

    return data


def render_rolling_risk(history):
    st.subheader("Rolling Risk")

    period = st.radio(
        "Rolling window",
        [
            "30 trading days",
            "90 trading days",
        ],
        horizontal=True,
        key="rolling_risk_window",
    )

    if period == "30 trading days":
        window = 30
    else:
        window = 90

    data = _rolling_risk(
        history,
        window,
    )

    col1, col2 = st.columns(2)

    with col1:

        _line_chart(
            data,
            [
                "rolling_beta",
            ],
            {
                "rolling_beta":
                    "Rolling beta",
            },
            "Rolling Portfolio Beta",
            "Beta",
        )

    with col2:

        _line_chart(
            data,
            [
                "rolling_volatility_pct",
            ],
            {
                "rolling_volatility_pct":
                    "Rolling volatility",
            },
            "Rolling Portfolio Volatility",
            "Annualised volatility %",
        )


# ------------------------------------------------------------
# Allocation
# ------------------------------------------------------------

def render_allocation_chart(holdings):
    holdings = _clean_holdings(
        holdings
    )

    st.subheader("Current Allocation")

    allocation = (
        holdings[
            [
                "display_ticker",
                "current_weight_pct",
            ]
        ]
        .dropna()
        .sort_values(
            "current_weight_pct",
            ascending=False,
        )
    )

    _bar_chart(
        allocation,
        "display_ticker",
        "current_weight_pct",
        "Current Portfolio Weights",
        "Weight %",
    )


# ------------------------------------------------------------
# Holding performance
# ------------------------------------------------------------

def render_holding_returns(holdings):
    holdings = _clean_holdings(
        holdings
    )

    st.subheader("Holding Performance")

    period = st.radio(
        "Holding return period",
        [
            "1 month",
            "3 months",
            "1 year",
        ],
        horizontal=True,
        key="holding_return_period",
    )

    column_map = {
        "1 month":
            "return_1m_pct",
        "3 months":
            "return_3m_pct",
        "1 year":
            "return_1y_pct",
    }

    return_column = (
        column_map[
            period
        ]
    )

    data = (
        holdings[
            [
                "display_ticker",
                return_column,
            ]
        ]
        .dropna()
        .sort_values(
            return_column,
            ascending=False,
        )
    )

    _bar_chart(
        data,
        "display_ticker",
        return_column,
        f"Current Holdings — {period} Return",
        "Return %",
    )


# ------------------------------------------------------------
# Beta contribution
# ------------------------------------------------------------

def render_beta_contribution(holdings):
    holdings = _clean_holdings(
        holdings
    )

    st.subheader("Beta Contribution")

    period = st.radio(
        "Beta period",
        [
            "1 month",
            "3 months",
            "1 year",
        ],
        horizontal=True,
        key="beta_period",
    )

    column_map = {
        "1 month":
            "beta_contribution_1m",
        "3 months":
            "beta_contribution_3m",
        "1 year":
            "beta_contribution_1y",
    }

    column = (
        column_map[
            period
        ]
    )

    data = (
        holdings[
            [
                "display_ticker",
                column,
            ]
        ]
        .dropna()
        .sort_values(
            column,
            ascending=False,
        )
    )

    _bar_chart(
        data,
        "display_ticker",
        column,
        f"Beta Contribution — {period}",
        "Beta contribution",
    )


# ------------------------------------------------------------
# Risk contribution
# ------------------------------------------------------------

def render_risk_contribution(holdings):
    holdings = _clean_holdings(
        holdings
    )

    st.subheader("Risk Contribution")

    period = st.radio(
        "Risk contribution period",
        [
            "1 month",
            "3 months",
            "1 year",
        ],
        horizontal=True,
        key="risk_contribution_period",
    )

    column_map = {
        "1 month":
            "risk_contribution_1m_pct",
        "3 months":
            "risk_contribution_3m_pct",
        "1 year":
            "risk_contribution_1y_pct",
    }

    column = (
        column_map[
            period
        ]
    )

    data = (
        holdings[
            [
                "display_ticker",
                column,
            ]
        ]
        .dropna()
        .sort_values(
            column,
            ascending=False,
        )
    )

    _bar_chart(
        data,
        "display_ticker",
        column,
        f"Portfolio Risk Contribution — {period}",
        "Risk contribution %",
    )


# ------------------------------------------------------------
# Complete dashboard chart section
# ------------------------------------------------------------

def render_all_charts(
    history,
    holdings,
):
    st.divider()

    st.header(
        "Portfolio Visual Analytics"
    )

    render_value_charts(
        history
    )

    st.divider()

    render_capital_chart(
        history
    )

    st.divider()

    render_profit_chart(
        history
    )

    st.divider()

    render_drawdown_chart(
        history
    )

    st.divider()

    render_rolling_risk(
        history
    )

    st.divider()

    render_allocation_chart(
        holdings
    )

    st.divider()

    render_holding_returns(
        holdings
    )

    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        render_beta_contribution(
            holdings
        )

    with col2:
        render_risk_contribution(
            holdings
        )