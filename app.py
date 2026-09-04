import streamlit as st

from trading212 import get_account_summary
from performance_metrics import get_performance_metrics
from return_metrics import get_return_metrics
from risk_metrics import get_risk_metrics


st.set_page_config(
    page_title="Portfolio Intelligence",
    page_icon="📈",
    layout="wide",
)


@st.cache_data(
    ttl=60,
    show_spinner=False,
)
def load_dashboard_data():

    performance_history, performance = (
        get_performance_metrics()
    )

    returns = get_return_metrics()

    risk = get_risk_metrics()

    live_account = get_account_summary()

    return (
        performance_history,
        performance,
        returns,
        risk,
        live_account,
    )


st.title("Portfolio Intelligence")

st.caption(
    "Trading 212 portfolio performance, "
    "benchmarking and risk analytics."
)


try:

    with st.spinner(
        "Loading portfolio data..."
    ):

        (
            history,
            performance,
            returns,
            risk,
            live,
        ) = load_dashboard_data()

except Exception as error:

    st.error(
        f"Unable to load portfolio data: {error}"
    )

    st.stop()


# ------------------------------------------------------------
# Live Trading 212 values
# ------------------------------------------------------------

live_total = float(
    live.get(
        "totalValue",
        performance[
            "portfolio_value_eur"
        ],
    )
)

investments = float(
    live.get(
        "investments",
        {},
    ).get(
        "currentValue",
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

st.subheader("Overview")

col1, col2, col3, col4 = st.columns(4)

with col1:

    st.metric(
        "Account value",
        f"€{live_total:,.2f}",
    )

with col2:

    st.metric(
        "Net capital invested",
        (
            f"€"
            f"{performance['net_capital_invested_eur']:,.2f}"
        ),
    )

with col3:

    st.metric(
        "Account gain",
        (
            f"€"
            f"{performance['simple_gain_eur']:,.2f}"
        ),
        (
            f"{performance['simple_return_pct']:.2f}%"
        ),
    )

with col4:

    st.metric(
        "Peak capital invested",
        (
            f"€"
            f"{performance['peak_net_capital_eur']:,.2f}"
        ),
    )


st.divider()


# ------------------------------------------------------------
# Performance
# ------------------------------------------------------------

st.subheader("Performance")

col1, col2, col3, col4 = st.columns(4)

with col1:

    st.metric(
        "Portfolio TWR",
        (
            f"{performance['portfolio_twr_pct']:.2f}%"
        ),
    )

with col2:

    st.metric(
        "S&P 500 TWR",
        (
            f"{performance['benchmark_twr_pct']:.2f}%"
        ),
    )

with col3:

    st.metric(
        "Outperformance",
        (
            f"{performance['relative_return_pp']:+.2f} pp"
        ),
    )

with col4:

    st.metric(
        "Portfolio CAGR",
        (
            f"{returns['portfolio_cagr_pct']:.2f}%"
        ),
    )


col1, col2, col3, col4 = st.columns(4)

with col1:

    st.metric(
        "Money-weighted return",
        (
            f"{returns['money_weighted_return_pct']:.2f}%"
        ),
    )

with col2:

    st.metric(
        "S&P 500 CAGR",
        (
            f"{returns['benchmark_cagr_pct']:.2f}%"
        ),
    )

with col3:

    st.metric(
        "S&P 500 MWR",
        (
            f"{returns['benchmark_mwr_pct']:.2f}%"
        ),
    )

with col4:

    st.metric(
        "Period",
        (
            f"{returns['elapsed_days']} days"
        ),
    )


st.divider()


# ------------------------------------------------------------
# Risk
# ------------------------------------------------------------

st.subheader("Risk")

col1, col2, col3, col4 = st.columns(4)

with col1:

    st.metric(
        "Annualised volatility",
        (
            f"{risk['annualised_volatility_pct']:.2f}%"
        ),
    )

with col2:

    st.metric(
        "Beta",
        f"{risk['beta']:.2f}",
    )

with col3:

    st.metric(
        "Sharpe ratio",
        f"{risk['sharpe_ratio']:.2f}",
    )

with col4:

    st.metric(
        "Sortino ratio",
        f"{risk['sortino_ratio']:.2f}",
    )


col1, col2, col3, col4 = st.columns(4)

with col1:

    st.metric(
        "Max drawdown",
        (
            f"{risk['max_drawdown_pct']:.2f}%"
        ),
    )

with col2:

    st.metric(
        "Longest drawdown",
        (
            f"{risk['max_drawdown_duration_days']} days"
        ),
    )

with col3:

    st.metric(
        "95% daily VaR",
        (
            f"{risk['historical_var_pct']:.2f}%"
        ),
    )

with col4:

    st.metric(
        "95% daily VaR",
        (
            f"€{risk['historical_var_eur']:,.2f}"
        ),
    )


# ------------------------------------------------------------
# Account reconciliation
# ------------------------------------------------------------

with st.expander(
    "Trading 212 account breakdown"
):

    col1, col2, col3, col4 = (
        st.columns(4)
    )

    with col1:

        st.metric(
            "Investments",
            f"€{investments:,.2f}",
        )

    with col2:

        st.metric(
            "Available cash",
            f"€{visible_cash:,.2f}",
        )

    with col3:

        st.metric(
            "Other balance",
            f"€{other_balance:,.2f}",
        )

    with col4:

        st.metric(
            "Total",
            f"€{live_total:,.2f}",
        )