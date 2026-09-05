import pandas as pd
import streamlit as st

from trading212 import get_account_summary
from performance_metrics import get_performance_metrics
from return_metrics import get_return_metrics
from period_analytics import get_all_period_analytics
from holdings_comparison import get_holdings_comparison


st.set_page_config(
    page_title="Portfolio Intelligence",
    page_icon="📈",
    layout="wide",
)


# ------------------------------------------------------------
# Formatting
# ------------------------------------------------------------

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
    labels = {
        "FULL": "Full history",
        "1Y": "1 year",
        "3M": "3 months",
        "1M": "1 month",
    }

    return labels.get(
        period,
        period,
    )


# ------------------------------------------------------------
# Data loading
# ------------------------------------------------------------

@st.cache_data(
    ttl=600,
    show_spinner=False,
)
def load_dashboard_data():

    performance_history, performance = (
        get_performance_metrics()
    )

    returns = get_return_metrics()

    live_account = get_account_summary()

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


# ------------------------------------------------------------
# Header
# ------------------------------------------------------------

header_col1, header_col2 = st.columns(
    [6, 1]
)

with header_col1:

    st.title(
        "Portfolio Intelligence"
    )

    st.caption(
        "Trading 212 portfolio performance, "
        "benchmarking and risk analytics."
    )

with header_col2:

    if st.button(
        "Refresh data",
        use_container_width=True,
    ):

        load_dashboard_data.clear()

        if (
            "dashboard_data"
            in st.session_state
        ):

            del st.session_state[
                "dashboard_data"
            ]

        st.rerun()


# ------------------------------------------------------------
# Load dashboard once
# ------------------------------------------------------------

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


# ------------------------------------------------------------
# Live account values
# ------------------------------------------------------------

live_total = float(
    live.get(
        "totalValue",
        performance[
            "portfolio_value_eur"
        ],
    )
)

investment_data = live.get(
    "investments",
    {},
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

cash_data = live.get(
    "cash",
    {},
)

available_cash = float(
    cash_data.get(
        "availableToTrade",
        0.0,
    )
)

reserved_cash = float(
    cash_data.get(
        "reservedForOrders",
        0.0,
    )
)

pie_cash = float(
    cash_data.get(
        "inPies",
        0.0,
    )
)

visible_cash = (
    available_cash
    + reserved_cash
    + pie_cash
)

other_balance = (
    live_total
    - investments
    - visible_cash
)


# ------------------------------------------------------------
# Overview
# ------------------------------------------------------------

st.subheader(
    "Overview"
)

col1, col2, col3, col4 = (
    st.columns(4)
)

with col1:

    st.metric(
        "Account value",
        format_eur(
            live_total
        ),
    )

with col2:

    st.metric(
        "Net capital invested",
        format_eur(
            performance[
                "net_capital_invested_eur"
            ]
        ),
    )

with col3:

    st.metric(
        "Total account gain",
        format_eur(
            performance[
                "simple_gain_eur"
            ]
        ),
        format_pct(
            performance[
                "simple_return_pct"
            ]
        ),
    )

with col4:

    st.metric(
        "Peak capital invested",
        format_eur(
            performance[
                "peak_net_capital_eur"
            ]
        ),
    )


col1, col2, col3, col4 = (
    st.columns(4)
)

with col1:

    st.metric(
        "Investments",
        format_eur(
            investments
        ),
    )

with col2:

    st.metric(
        "Available cash",
        format_eur(
            visible_cash
        ),
    )

with col3:

    st.metric(
        "Other balance",
        format_eur(
            other_balance
        ),
    )

with col4:

    st.metric(
        "Unrealised P/L",
        format_eur(
            unrealised_pnl
        ),
    )


st.divider()


# ------------------------------------------------------------
# Actual historical portfolio
# ------------------------------------------------------------

st.subheader(
    "Actual Portfolio Analytics"
)

st.caption(
    "Performance and risk based on the positions "
    "and weights you actually held during each period."
)


selected_period = st.radio(
    "Analysis period",
    options=[
        "FULL",
        "1Y",
        "3M",
        "1M",
    ],
    horizontal=True,
    format_func=period_label,
    key="actual_portfolio_period",
)


period_rows = period_table[
    period_table[
        "period"
    ] == selected_period
]


if period_rows.empty:

    st.error(
        "No analytics are available "
        "for this period."
    )

    st.stop()


selected = (
    period_rows.iloc[0]
)


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


# ------------------------------------------------------------
# Performance
# ------------------------------------------------------------

st.markdown(
    "### Performance"
)


col1, col2, col3, col4 = (
    st.columns(4)
)

with col1:

    st.metric(
        "Portfolio return (TWR)",
        format_pct(
            selected[
                "portfolio_twr_pct"
            ]
        ),
    )

with col2:

    st.metric(
        "Investment profit",
        format_eur(
            selected[
                "portfolio_profit_eur"
            ]
        ),
    )

with col3:

    st.metric(
        "S&P 500 return",
        format_pct(
            selected[
                "benchmark_twr_pct"
            ]
        ),
    )

with col4:

    st.metric(
        "Outperformance",
        format_pp(
            selected[
                "relative_return_pp"
            ]
        ),
    )


col1, col2, col3, col4 = (
    st.columns(4)
)

with col1:

    st.metric(
        "Portfolio CAGR",
        format_pct(
            selected[
                "portfolio_cagr_pct"
            ]
        ),
    )

with col2:

    st.metric(
        "S&P 500 CAGR",
        format_pct(
            selected[
                "benchmark_cagr_pct"
            ]
        ),
    )

with col3:

    st.metric(
        "Best portfolio day",
        format_pct(
            selected[
                "best_day_pct"
            ]
        ),
    )

with col4:

    st.metric(
        "Worst portfolio day",
        format_pct(
            selected[
                "worst_day_pct"
            ]
        ),
    )


if selected_period == "FULL":

    col1, col2, col3, col4 = (
        st.columns(4)
    )

    with col1:

        st.metric(
            "Money-weighted return",
            format_pct(
                returns[
                    "money_weighted_return_pct"
                ]
            ),
        )

    with col2:

        st.metric(
            "S&P 500 MWR",
            format_pct(
                returns[
                    "benchmark_mwr_pct"
                ]
            ),
        )

    with col3:

        st.metric(
            "History length",
            (
                f"{returns['elapsed_days']} "
                f"days"
            ),
        )

    with col4:

        st.metric(
            "External cash flow",
            format_eur(
                selected[
                    "external_flows_eur"
                ]
            ),
        )


# ------------------------------------------------------------
# Risk
# ------------------------------------------------------------

st.markdown(
    "### Risk"
)

st.caption(
    "Your portfolio risk is shown directly beside "
    "the S&P 500 where a useful comparison exists."
)


col1, col2, col3, col4 = (
    st.columns(4)
)

with col1:

    st.metric(
        "Portfolio volatility",
        format_pct(
            selected[
                "annualised_volatility_pct"
            ]
        ),
    )

with col2:

    st.metric(
        "S&P 500 volatility",
        format_pct(
            selected[
                "benchmark_volatility_pct"
            ]
        ),
    )

with col3:

    st.metric(
        "Portfolio beta",
        format_number(
            selected[
                "beta"
            ]
        ),
    )

with col4:

    st.metric(
        "Correlation to S&P 500",
        format_number(
            selected[
                "correlation"
            ]
        ),
    )


col1, col2, col3, col4 = (
    st.columns(4)
)

with col1:

    st.metric(
        "Portfolio max drawdown",
        format_pct(
            selected[
                "max_drawdown_pct"
            ]
        ),
    )

with col2:

    st.metric(
        "S&P 500 max drawdown",
        format_pct(
            selected[
                "benchmark_max_drawdown_pct"
            ]
        ),
    )

with col3:

    st.metric(
        "Portfolio drawdown duration",
        (
            f"{int(selected['max_drawdown_duration_days'])} "
            f"days"
        ),
    )

with col4:

    st.metric(
        "S&P drawdown duration",
        (
            f"{int(selected['benchmark_drawdown_duration_days'])} "
            f"days"
        ),
    )


col1, col2, col3, col4 = (
    st.columns(4)
)

with col1:

    st.metric(
        "Sharpe ratio",
        format_number(
            selected[
                "sharpe_ratio"
            ]
        ),
    )

with col2:

    st.metric(
        "Sortino ratio",
        format_number(
            selected[
                "sortino_ratio"
            ]
        ),
    )

with col3:

    st.metric(
        "95% daily VaR",
        format_pct(
            selected[
                "historical_var_pct"
            ]
        ),
    )

with col4:

    st.metric(
        "95% daily VaR",
        format_eur(
            selected[
                "historical_var_eur"
            ]
        ),
    )


# ------------------------------------------------------------
# Period comparison
# ------------------------------------------------------------

with st.expander(
    "Compare all periods"
):

    comparison_display = period_table[
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
    ].copy()


    comparison_display[
        "period"
    ] = comparison_display[
        "period"
    ].map(
        period_label
    )


    comparison_display = (
        comparison_display.rename(
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
        .round(2)
    )


    st.dataframe(
        comparison_display,
        hide_index=True,
        use_container_width=True,
    )


st.divider()


# ------------------------------------------------------------
# Current holdings hypothetical backtest
# ------------------------------------------------------------

with st.expander(
    "Current Holdings Backtest — Hypothetical"
):

    st.caption(
        "This takes the portfolio you own today, "
        "keeps today's weights constant, and asks "
        "how that exact portfolio would have behaved "
        "historically. It is not your actual past performance."
    )


    current_period = st.radio(
        "Backtest period",
        options=[
            "1M",
            "3M",
            "1Y",
        ],
        horizontal=True,
        format_func=period_label,
        key="current_holdings_backtest_period",
    )


    current_rows = (
        current_holdings_table[
            current_holdings_table[
                "period"
            ] == current_period
        ]
    )

    actual_rows = (
        period_table[
            period_table[
                "period"
            ] == current_period
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


        st.markdown(
            "### Portfolio Comparison"
        )


        col1, col2, col3, col4 = (
            st.columns(4)
        )

        with col1:

            st.metric(
                "Actual portfolio beta",
                format_number(
                    actual[
                        "beta"
                    ]
                ),
            )

        with col2:

            st.metric(
                "Current holdings beta",
                format_number(
                    current[
                        "beta"
                    ]
                ),
            )

        with col3:

            st.metric(
                "Actual volatility",
                format_pct(
                    actual[
                        "annualised_volatility_pct"
                    ]
                ),
            )

        with col4:

            st.metric(
                "Current holdings volatility",
                format_pct(
                    current[
                        "annualised_volatility_pct"
                    ]
                ),
            )


        col1, col2, col3, col4 = (
            st.columns(4)
        )

        with col1:

            st.metric(
                "Hypothetical return",
                format_pct(
                    current[
                        "current_portfolio_return_pct"
                    ]
                ),
            )

        with col2:

            st.metric(
                "S&P 500 return",
                format_pct(
                    current[
                        "benchmark_return_pct"
                    ]
                ),
            )

        with col3:

            st.metric(
                "Hypothetical Sharpe",
                format_number(
                    current[
                        "sharpe_ratio"
                    ]
                ),
            )

        with col4:

            st.metric(
                "Hypothetical drawdown",
                format_pct(
                    current[
                        "max_drawdown_pct"
                    ]
                ),
            )


    st.markdown(
        "### Current Holding Risk Breakdown"
    )


    suffix = (
        current_period.lower()
    )


    holding_columns = [
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


    holding_display = (
        holdings_table[
            holding_columns
        ]
        .copy()
    )


    holding_display = (
        holding_display.rename(
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
                    "Hypothetical Return %",

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


    numeric_columns = [
        "Value €",
        "Weight %",
        "Hypothetical Return %",
        "Beta",
        "Beta Contribution",
        "Volatility %",
        "S&P Correlation",
        "Risk Contribution %",
    ]


    holding_display[
        numeric_columns
    ] = holding_display[
        numeric_columns
    ].round(2)


    st.dataframe(
        holding_display,
        hide_index=True,
        use_container_width=True,
    )


    st.caption(
        "Holding statistics use today's positions "
        "and today's portfolio weights."
    )