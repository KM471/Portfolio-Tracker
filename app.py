import pandas as pd
import streamlit as st
import altair as alt

from trading212 import get_account_summary
from performance_metrics import get_performance_metrics
from return_metrics import get_return_metrics
from period_analytics import get_all_period_analytics
from holdings_comparison import get_holdings_comparison
from dashboard_charts import (
    render_value_charts,
    render_capital_chart,
    render_profit_chart,
    render_drawdown_chart,
    render_rolling_risk,
    render_allocation_chart,
    render_holding_returns,
    render_beta_contribution,
    render_risk_contribution,
)


st.set_page_config(
    page_title="Portfolio Intelligence",
    page_icon="📈",
    layout="wide",
)


# ============================================================
# Formatting helpers
# ============================================================

def format_pct(value):
    if pd.isna(value):
        return "N/A"

    return f"{float(value):.2f}%"


def format_number(value):
    if pd.isna(value):
        return "N/A"

    return f"{float(value):.2f}"


def format_eur(value):
    if pd.isna(value):
        return "N/A"

    return f"€{float(value):,.2f}"


def format_pp(value):
    if pd.isna(value):
        return "N/A"

    return f"{float(value):+.2f} pp"


def period_label(period):
    return {
        "FULL": "Full history",
        "1Y": "1 year",
        "3M": "3 months",
        "1M": "1 month",
    }.get(
        period,
        period,
    )


def get_period_row(
    period_table,
    period,
):
    rows = period_table[
        period_table[
            "period"
        ] == period
    ]

    if rows.empty:
        return None

    return rows.iloc[0]


def metric_row(items):
    columns = st.columns(
        len(items)
    )

    for column, item in zip(
        columns,
        items,
    ):
        label = item[0]
        value = item[1]

        delta = (
            item[2]
            if len(item) > 2
            else None
        )

        with column:
            st.metric(
                label,
                value,
                delta,
            )


# ============================================================
# Compact allocation chart
# ============================================================

def render_compact_allocation(
    holdings,
):

    allocation = (
        holdings[
            [
                "display_ticker",
                "current_value_eur",
                "current_weight_pct",
            ]
        ]
        .copy()
        .dropna(
            subset=[
                "display_ticker",
                "current_weight_pct",
            ]
        )
        .sort_values(
            "current_weight_pct",
            ascending=False,
        )
        .reset_index(
            drop=True
        )
    )

    if allocation.empty:
        st.info(
            "No current holdings available."
        )
        return

    # Keep the front page chart simple.
    # Show the five largest positions
    # and combine the remainder as Other.
    if len(allocation) > 5:

        top = allocation.head(
            5
        ).copy()

        remainder = allocation.iloc[
            5:
        ]

        other = pd.DataFrame(
            {
                "display_ticker": [
                    "Other"
                ],
                "current_value_eur": [
                    remainder[
                        "current_value_eur"
                    ].sum()
                ],
                "current_weight_pct": [
                    remainder[
                        "current_weight_pct"
                    ].sum()
                ],
            }
        )

        allocation = pd.concat(
            [
                top,
                other,
            ],
            ignore_index=True,
        )

    chart = (
        alt.Chart(
            allocation
        )
        .mark_arc(
            innerRadius=55,
        )
        .encode(
            theta=alt.Theta(
                "current_weight_pct:Q"
            ),
            color=alt.Color(
                "display_ticker:N",
                title=None,
                legend=alt.Legend(
                    orient="bottom",
                    columns=3,
                ),
            ),
            tooltip=[
                alt.Tooltip(
                    "display_ticker:N",
                    title="Holding",
                ),
                alt.Tooltip(
                    "current_weight_pct:Q",
                    title="Weight",
                    format=".1f",
                ),
                alt.Tooltip(
                    "current_value_eur:Q",
                    title="Value €",
                    format=",.2f",
                ),
            ],
        )
        .properties(
            height=240,
        )
    )

    st.altair_chart(
        chart,
        use_container_width=True,
    )


# ============================================================
# Data loading
# ============================================================

@st.cache_data(
    ttl=600,
    show_spinner=False,
)
def load_dashboard_data():

    performance_history, performance = (
        get_performance_metrics()
    )

    returns = (
        get_return_metrics()
    )

    live_account = (
        get_account_summary()
    )

    period_analytics = (
        get_all_period_analytics()
    )

    (
        current_holdings_summary,
        holdings_comparison,
    ) = get_holdings_comparison()

    return (
        performance_history,
        performance,
        returns,
        live_account,
        period_analytics,
        current_holdings_summary,
        holdings_comparison,
    )


# ============================================================
# Header
# ============================================================

header_left, header_right = (
    st.columns(
        [6, 1]
    )
)


with header_left:

    st.title(
        "Portfolio Intelligence"
    )

    st.caption(
        "Trading 212 portfolio performance, "
        "benchmarking and risk analytics."
    )


with header_right:

    if st.button(
        "Refresh data",
        use_container_width=True,
    ):

        load_dashboard_data.clear()

        st.session_state.pop(
            "dashboard_data",
            None,
        )

        st.rerun()


# ============================================================
# Load dashboard
# ============================================================

if (
    "dashboard_data"
    not in st.session_state
):

    try:

        with st.spinner(
            "Loading portfolio data..."
        ):

            st.session_state[
                "dashboard_data"
            ] = load_dashboard_data()

    except Exception as error:

        st.error(
            f"Unable to load portfolio data: "
            f"{error}"
        )

        st.stop()


(
    history,
    performance,
    returns,
    live,
    period_table,
    current_holdings_table,
    holdings_table,
) = st.session_state[
    "dashboard_data"
]


# ============================================================
# Live account values
# ============================================================

live_total = float(
    live.get(
        "totalValue",
        performance[
            "portfolio_value_eur"
        ],
    )
)


investment_data = (
    live.get(
        "investments",
        {},
    )
)


investments = float(
    investment_data.get(
        "currentValue",
        0.0,
    )
)


unrealised_pnl = float(
    investment_data.get(
        "unrealizedProfitLoss",
        0.0,
    )
)


cash_data = (
    live.get(
        "cash",
        {},
    )
)


visible_cash = (
    float(
        cash_data.get(
            "availableToTrade",
            0.0,
        )
    )
    +
    float(
        cash_data.get(
            "reservedForOrders",
            0.0,
        )
    )
    +
    float(
        cash_data.get(
            "inPies",
            0.0,
        )
    )
)


other_balance = (
    live_total
    - investments
    - visible_cash
)


# ============================================================
# MAIN DASHBOARD
# ============================================================


# ------------------------------------------------------------
# Overview
# ------------------------------------------------------------

st.subheader(
    "Overview"
)


overview_left, overview_right = (
    st.columns(
        [
            3.2,
            1.25,
        ]
    )
)


with overview_left:

    st.caption(
        "TWR measures investment performance independently "
        "of deposits and withdrawals."
    )

    row1 = st.columns(
        3
    )

    with row1[0]:

        st.metric(
            "Account value",
            format_eur(
                live_total
            ),
        )

    with row1[1]:

        st.metric(
            "Portfolio TWR",
            format_pct(
                performance[
                    "portfolio_twr_pct"
                ]
            ),
        )

    with row1[2]:

        st.metric(
            "Investment profit",
            format_eur(
                performance[
                    "simple_gain_eur"
                ]
            ),
        )


    row2 = st.columns(
        3
    )

    with row2[0]:

        st.metric(
            "Net capital invested",
            format_eur(
                performance[
                    "net_capital_invested_eur"
                ]
            ),
        )

    with row2[1]:

        st.metric(
            "Money-weighted return",
            format_pct(
                returns[
                    "money_weighted_return_pct"
                ]
            ),
        )

    with row2[2]:

        st.metric(
            "Unrealised P/L",
            format_eur(
                unrealised_pnl
            ),
        )


with overview_right:

    st.markdown(
        "**Current allocation**"
    )

    render_compact_allocation(
        holdings_table
    )


# ------------------------------------------------------------
# Recent performance
# ------------------------------------------------------------

st.markdown(
    "**Recent performance**"
)


row_1m = (
    get_period_row(
        period_table,
        "1M",
    )
)

row_3m = (
    get_period_row(
        period_table,
        "3M",
    )
)

row_1y = (
    get_period_row(
        period_table,
        "1Y",
    )
)


recent_items = []


if row_1m is not None:

    recent_items.append(
        (
            "1 month",
            format_pct(
                row_1m[
                    "portfolio_twr_pct"
                ]
            ),
            (
                f"{row_1m['relative_return_pp']:+.2f} pp vs S&P"
            ),
        )
    )


if row_3m is not None:

    recent_items.append(
        (
            "3 months",
            format_pct(
                row_3m[
                    "portfolio_twr_pct"
                ]
            ),
            (
                f"{row_3m['relative_return_pp']:+.2f} pp vs S&P"
            ),
        )
    )


if row_1y is not None:

    recent_items.append(
        (
            "1 year",
            format_pct(
                row_1y[
                    "portfolio_twr_pct"
                ]
            ),
            (
                f"{row_1y['relative_return_pp']:+.2f} pp vs S&P"
            ),
        )
    )


recent_items.append(
    (
        "Full-history CAGR",
        format_pct(
            returns[
                "portfolio_cagr_pct"
            ]
        ),
    )
)


metric_row(
    recent_items
)


# ------------------------------------------------------------
# Account details
# ------------------------------------------------------------

with st.expander(
    "Account details"
):

    metric_row(
        [
            (
                "Investments",
                format_eur(
                    investments
                ),
            ),
            (
                "Available cash",
                format_eur(
                    visible_cash
                ),
            ),
            (
                "Peak capital invested",
                format_eur(
                    performance[
                        "peak_net_capital_eur"
                    ]
                ),
            ),
            (
                "Other balance",
                format_eur(
                    other_balance
                ),
            ),
        ]
    )


st.divider()


# ------------------------------------------------------------
# Benchmark
# ------------------------------------------------------------

st.subheader(
    "S&P 500 Benchmark"
)


metric_row(
    [
        (
            "Portfolio TWR",
            format_pct(
                performance[
                    "portfolio_twr_pct"
                ]
            ),
        ),
        (
            "S&P 500 TWR",
            format_pct(
                performance[
                    "benchmark_twr_pct"
                ]
            ),
        ),
        (
            "Outperformance",
            format_pp(
                performance[
                    "relative_return_pp"
                ]
            ),
        ),
    ]
)


render_value_charts(
    history
)


st.divider()


# ============================================================
# DETAILED ANALYTICS
# ============================================================


# ------------------------------------------------------------
# Detailed performance + risk
# ------------------------------------------------------------

with st.expander(
    "Detailed Performance & Risk Analytics"
):

    st.caption(
        "Historical performance and risk statistics "
        "for the actual portfolio held during each period."
    )


    period = st.radio(
        "Analysis period",
        [
            "FULL",
            "1Y",
            "3M",
            "1M",
        ],
        horizontal=True,
        format_func=period_label,
        key="detailed_period",
    )


    selected = (
        get_period_row(
            period_table,
            period,
        )
    )


    if selected is not None:

        first_date = pd.to_datetime(
            selected[
                "first_date"
            ]
        ).date()

        last_date = pd.to_datetime(
            selected[
                "last_date"
            ]
        ).date()


        st.caption(
            f"{first_date} → {last_date} | "
            f"{int(selected['trading_observations'])} "
            f"trading observations"
        )


        st.markdown(
            "#### Performance"
        )


        metric_row(
            [
                (
                    "Portfolio return (TWR)",
                    format_pct(
                        selected[
                            "portfolio_twr_pct"
                        ]
                    ),
                ),
                (
                    "Investment profit",
                    format_eur(
                        selected[
                            "portfolio_profit_eur"
                        ]
                    ),
                ),
                (
                    "S&P 500 return",
                    format_pct(
                        selected[
                            "benchmark_twr_pct"
                        ]
                    ),
                ),
                (
                    "Outperformance",
                    format_pp(
                        selected[
                            "relative_return_pp"
                        ]
                    ),
                ),
            ]
        )


        metric_row(
            [
                (
                    "Portfolio CAGR",
                    format_pct(
                        selected[
                            "portfolio_cagr_pct"
                        ]
                    ),
                ),
                (
                    "S&P 500 CAGR",
                    format_pct(
                        selected[
                            "benchmark_cagr_pct"
                        ]
                    ),
                ),
                (
                    "Best portfolio day",
                    format_pct(
                        selected[
                            "best_day_pct"
                        ]
                    ),
                ),
                (
                    "Worst portfolio day",
                    format_pct(
                        selected[
                            "worst_day_pct"
                        ]
                    ),
                ),
            ]
        )


        if period == "FULL":

            metric_row(
                [
                    (
                        "Money-weighted return",
                        format_pct(
                            returns[
                                "money_weighted_return_pct"
                            ]
                        ),
                    ),
                    (
                        "S&P 500 MWR",
                        format_pct(
                            returns[
                                "benchmark_mwr_pct"
                            ]
                        ),
                    ),
                    (
                        "History length",
                        (
                            f"{returns['elapsed_days']} days"
                        ),
                    ),
                    (
                        "External cash flow",
                        format_eur(
                            selected[
                                "external_flows_eur"
                            ]
                        ),
                    ),
                ]
            )


        st.markdown(
            "#### Risk"
        )


        metric_row(
            [
                (
                    "Portfolio volatility",
                    format_pct(
                        selected[
                            "annualised_volatility_pct"
                        ]
                    ),
                ),
                (
                    "S&P 500 volatility",
                    format_pct(
                        selected[
                            "benchmark_volatility_pct"
                        ]
                    ),
                ),
                (
                    "Portfolio beta",
                    format_number(
                        selected[
                            "beta"
                        ]
                    ),
                ),
                (
                    "Correlation to S&P 500",
                    format_number(
                        selected[
                            "correlation"
                        ]
                    ),
                ),
            ]
        )


        metric_row(
            [
                (
                    "Portfolio max drawdown",
                    format_pct(
                        selected[
                            "max_drawdown_pct"
                        ]
                    ),
                ),
                (
                    "S&P max drawdown",
                    format_pct(
                        selected[
                            "benchmark_max_drawdown_pct"
                        ]
                    ),
                ),
                (
                    "Portfolio drawdown duration",
                    (
                        f"{int(selected['max_drawdown_duration_days'])} days"
                    ),
                ),
                (
                    "S&P drawdown duration",
                    (
                        f"{int(selected['benchmark_drawdown_duration_days'])} days"
                    ),
                ),
            ]
        )


        metric_row(
            [
                (
                    "Sharpe ratio",
                    format_number(
                        selected[
                            "sharpe_ratio"
                        ]
                    ),
                ),
                (
                    "Sortino ratio",
                    format_number(
                        selected[
                            "sortino_ratio"
                        ]
                    ),
                ),
                (
                    "95% daily VaR",
                    format_pct(
                        selected[
                            "historical_var_pct"
                        ]
                    ),
                ),
                (
                    "95% daily VaR",
                    format_eur(
                        selected[
                            "historical_var_eur"
                        ]
                    ),
                ),
            ]
        )


        st.markdown(
            "#### Risk Charts"
        )


        render_drawdown_chart(
            history
        )


        render_rolling_risk(
            history
        )


        st.markdown(
            "#### Compare All Periods"
        )


        compare = (
            period_table[
                [
                    "period",
                    "portfolio_twr_pct",
                    "benchmark_twr_pct",
                    "relative_return_pp",
                    "annualised_volatility_pct",
                    "benchmark_volatility_pct",
                    "beta",
                    "correlation",
                    "sharpe_ratio",
                    "sortino_ratio",
                    "max_drawdown_pct",
                    "benchmark_max_drawdown_pct",
                ]
            ]
            .copy()
            .rename(
                columns={
                    "period":
                        "Period",
                    "portfolio_twr_pct":
                        "Portfolio Return %",
                    "benchmark_twr_pct":
                        "S&P Return %",
                    "relative_return_pp":
                        "Outperformance pp",
                    "annualised_volatility_pct":
                        "Portfolio Volatility %",
                    "benchmark_volatility_pct":
                        "S&P Volatility %",
                    "beta":
                        "Beta",
                    "correlation":
                        "S&P Correlation",
                    "sharpe_ratio":
                        "Sharpe",
                    "sortino_ratio":
                        "Sortino",
                    "max_drawdown_pct":
                        "Portfolio Drawdown %",
                    "benchmark_max_drawdown_pct":
                        "S&P Drawdown %",
                }
            )
        )


        compare[
            "Period"
        ] = compare[
            "Period"
        ].map(
            period_label
        )


        st.dataframe(
            compare.round(2),
            hide_index=True,
            use_container_width=True,
        )


# ------------------------------------------------------------
# Capital and profit
# ------------------------------------------------------------

with st.expander(
    "Capital & Profit History"
):

    st.caption(
        "Tracks invested capital and investment profit "
        "through deposits and withdrawals."
    )


    render_capital_chart(
        history
    )


    render_profit_chart(
        history
    )


# ------------------------------------------------------------
# Holdings analytics
# ------------------------------------------------------------

with st.expander(
    "Current Holdings & Risk Breakdown"
):

    st.caption(
        "Detailed analytics for the positions currently "
        "held in the portfolio."
    )


    render_allocation_chart(
        holdings_table
    )


    render_holding_returns(
        holdings_table
    )


    col1, col2 = (
        st.columns(2)
    )


    with col1:

        render_beta_contribution(
            holdings_table
        )


    with col2:

        render_risk_contribution(
            holdings_table
        )


    st.markdown(
        "#### Full Holding Statistics"
    )


    holding_period = st.radio(
        "Holding statistics period",
        [
            "1M",
            "3M",
            "1Y",
        ],
        horizontal=True,
        format_func=period_label,
        key="holding_period",
    )


    suffix = (
        holding_period.lower()
    )


    holding_display = (
        holdings_table[
            [
                "display_ticker",
                "company",
                "current_value_eur",
                "current_weight_pct",
                f"return_{suffix}_pct",
                f"beta_{suffix}",
                f"beta_contribution_{suffix}",
                f"volatility_{suffix}_pct",
                f"correlation_{suffix}",
                f"risk_contribution_{suffix}_pct",
            ]
        ]
        .copy()
        .rename(
            columns={
                "display_ticker":
                    "Ticker",
                "company":
                    "Company",
                "current_value_eur":
                    "Value €",
                "current_weight_pct":
                    "Weight %",
                f"return_{suffix}_pct":
                    "Return %",
                f"beta_{suffix}":
                    "Beta",
                f"beta_contribution_{suffix}":
                    "Beta Contribution",
                f"volatility_{suffix}_pct":
                    "Volatility %",
                f"correlation_{suffix}":
                    "S&P Correlation",
                f"risk_contribution_{suffix}_pct":
                    "Risk Contribution %",
            }
        )
    )


    st.dataframe(
        holding_display.round(2),
        hide_index=True,
        use_container_width=True,
    )


# ------------------------------------------------------------
# Current holdings hypothetical backtest
# ------------------------------------------------------------

with st.expander(
    "Current Holdings Backtest — Hypothetical"
):

    st.caption(
        "This is not your actual historical performance. "
        "It holds today's positions and weights constant "
        "through the selected historical period."
    )


    backtest_period = st.radio(
        "Backtest period",
        [
            "1M",
            "3M",
            "1Y",
        ],
        horizontal=True,
        format_func=period_label,
        key="backtest_period",
    )


    current_rows = (
        current_holdings_table[
            current_holdings_table[
                "period"
            ] == backtest_period
        ]
    )


    actual_rows = (
        period_table[
            period_table[
                "period"
            ] == backtest_period
        ]
    )


    if (
        not current_rows.empty
        and not actual_rows.empty
    ):

        current = (
            current_rows.iloc[0]
        )

        actual = (
            actual_rows.iloc[0]
        )


        metric_row(
            [
                (
                    "Actual portfolio beta",
                    format_number(
                        actual[
                            "beta"
                        ]
                    ),
                ),
                (
                    "Current holdings beta",
                    format_number(
                        current[
                            "beta"
                        ]
                    ),
                ),
                (
                    "Actual volatility",
                    format_pct(
                        actual[
                            "annualised_volatility_pct"
                        ]
                    ),
                ),
                (
                    "Current holdings volatility",
                    format_pct(
                        current[
                            "annualised_volatility_pct"
                        ]
                    ),
                ),
            ]
        )


        metric_row(
            [
                (
                    "Hypothetical return",
                    format_pct(
                        current[
                            "current_portfolio_return_pct"
                        ]
                    ),
                ),
                (
                    "S&P 500 return",
                    format_pct(
                        current[
                            "benchmark_return_pct"
                        ]
                    ),
                ),
                (
                    "Hypothetical Sharpe",
                    format_number(
                        current[
                            "sharpe_ratio"
                        ]
                    ),
                ),
                (
                    "Hypothetical drawdown",
                    format_pct(
                        current[
                            "max_drawdown_pct"
                        ]
                    ),
                ),
            ]
        )