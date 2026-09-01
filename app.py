import altair as alt
import streamlit as st

from trading212 import get_account_summary, get_positions


st.set_page_config(
    page_title="Portfolio Intelligence",
    page_icon="📊",
    layout="wide",
)


@st.cache_data(ttl=30, show_spinner=False)
def load_portfolio_data():
    account = get_account_summary()
    positions = get_positions()

    return account, positions


title_col, refresh_col = st.columns([6, 1])

with title_col:
    st.title("Portfolio Intelligence")
    st.caption("Live portfolio data from Trading 212")

with refresh_col:
    if st.button("Refresh"):
        st.cache_data.clear()
        st.rerun()


try:
    with st.spinner("Loading portfolio..."):
        account, portfolio = load_portfolio_data()

except Exception as error:
    st.error("Could not load Trading 212 data.")
    st.exception(error)
    st.stop()


if portfolio.empty:
    st.warning("No open positions were found.")
    st.stop()


currency = account["currency"]

currency_symbols = {
    "EUR": "€",
    "USD": "$",
    "GBP": "£",
}

currency_symbol = currency_symbols.get(
    currency,
    f"{currency} ",
)


total_value = account["totalValue"]

cash_available = account["cash"]["availableToTrade"]

investment_value = account["investments"]["currentValue"]

investment_cost = account["investments"]["totalCost"]

total_unrealised_pnl = account["investments"][
    "unrealizedProfitLoss"
]


if investment_cost:
    portfolio_return_pct = (
        total_unrealised_pnl / investment_cost
    )
else:
    portfolio_return_pct = 0


if investment_value:
    portfolio["weight"] = (
        portfolio["current_value"] / investment_value
    )
else:
    portfolio["weight"] = 0


portfolio["return_pct"] = portfolio.apply(
    lambda row: (
        row["unrealised_pnl"] / row["total_cost"]
        if row["total_cost"]
        else 0
    ),
    axis=1,
)


largest_position = portfolio.loc[
    portfolio["current_value"].idxmax()
]

top_three_weight = (
    portfolio
    .nlargest(3, "current_value")["weight"]
    .sum()
)


metric1, metric2, metric3, metric4 = st.columns(4)

metric1.metric(
    label="Total Account Value",
    value=f"{currency_symbol}{total_value:,.2f}",
)

metric2.metric(
    label="Investments",
    value=f"{currency_symbol}{investment_value:,.2f}",
)

metric3.metric(
    label="Unrealised P/L",
    value=f"{currency_symbol}{total_unrealised_pnl:,.2f}",
    delta=f"{portfolio_return_pct:.2%}",
)

metric4.metric(
    label="Available Cash",
    value=f"{currency_symbol}{cash_available:,.2f}",
)


st.divider()


metric5, metric6, metric7 = st.columns(3)

metric5.metric(
    label="Open Positions",
    value=len(portfolio),
)

metric6.metric(
    label="Largest Position",
    value=largest_position["display_ticker"],
    delta=f"{largest_position['weight']:.1%} of portfolio",
)

metric7.metric(
    label="Top 3 Concentration",
    value=f"{top_three_weight:.1%}",
)


st.subheader("Portfolio Overview")


chart1, chart2 = st.columns(2)


with chart1:
    st.markdown("#### Allocation")

    allocation_chart = (
        alt.Chart(portfolio)
        .mark_arc(innerRadius=70)
        .encode(
            theta=alt.Theta(
                "current_value:Q",
                title="Current Value",
            ),
            color=alt.Color(
                "display_ticker:N",
                title="Holding",
            ),
            tooltip=[
                alt.Tooltip(
                    "display_ticker:N",
                    title="Ticker",
                ),
                alt.Tooltip(
                    "company:N",
                    title="Company",
                ),
                alt.Tooltip(
                    "current_value:Q",
                    title="Value",
                    format=",.2f",
                ),
                alt.Tooltip(
                    "weight:Q",
                    title="Weight",
                    format=".1%",
                ),
            ],
        )
        .properties(
            height=350,
        )
    )

    st.altair_chart(
        allocation_chart,
        width="stretch",
    )


with chart2:
    st.markdown("#### Unrealised P/L by Holding")

    pnl_chart = (
        alt.Chart(portfolio)
        .mark_bar()
        .encode(
            x=alt.X(
                "unrealised_pnl:Q",
                title=f"Unrealised P/L ({currency})",
            ),
            y=alt.Y(
                "display_ticker:N",
                title=None,
                sort="-x",
            ),
            color=alt.Color(
                "unrealised_pnl:Q",
                title="P/L",
                scale=alt.Scale(
                    scheme="redyellowgreen"
                ),
            ),
            tooltip=[
                alt.Tooltip(
                    "display_ticker:N",
                    title="Ticker",
                ),
                alt.Tooltip(
                    "company:N",
                    title="Company",
                ),
                alt.Tooltip(
                    "unrealised_pnl:Q",
                    title="P/L",
                    format=",.2f",
                ),
                alt.Tooltip(
                    "return_pct:Q",
                    title="Return",
                    format=".2%",
                ),
            ],
        )
        .properties(
            height=350,
        )
    )

    st.altair_chart(
        pnl_chart,
        width="stretch",
    )


st.divider()

st.subheader("Current Holdings")


display_portfolio = portfolio[
    [
        "display_ticker",
        "company",
        "quantity",
        "instrument_currency",
        "average_price",
        "current_price",
        "total_cost",
        "current_value",
        "unrealised_pnl",
        "return_pct",
        "weight",
    ]
].copy()


display_portfolio["Average Price"] = display_portfolio.apply(
    lambda row: (
        f"{row['instrument_currency']} "
        f"{row['average_price']:,.2f}"
    ),
    axis=1,
)

display_portfolio["Current Price"] = display_portfolio.apply(
    lambda row: (
        f"{row['instrument_currency']} "
        f"{row['current_price']:,.2f}"
    ),
    axis=1,
)

display_portfolio["Cost"] = display_portfolio[
    "total_cost"
].map(
    lambda value: f"{currency_symbol}{value:,.2f}"
)

display_portfolio["Current Value"] = display_portfolio[
    "current_value"
].map(
    lambda value: f"{currency_symbol}{value:,.2f}"
)

display_portfolio["Unrealised P/L"] = display_portfolio[
    "unrealised_pnl"
].map(
    lambda value: f"{currency_symbol}{value:,.2f}"
)

display_portfolio["Return"] = display_portfolio[
    "return_pct"
].map(
    lambda value: f"{value:.2%}"
)

display_portfolio["Weight"] = display_portfolio[
    "weight"
].map(
    lambda value: f"{value:.2%}"
)


display_portfolio = display_portfolio[
    [
        "display_ticker",
        "company",
        "quantity",
        "Average Price",
        "Current Price",
        "Cost",
        "Current Value",
        "Unrealised P/L",
        "Return",
        "Weight",
    ]
]


display_portfolio.columns = [
    "Ticker",
    "Company",
    "Quantity",
    "Average Price",
    "Current Price",
    "Cost",
    "Current Value",
    "Unrealised P/L",
    "Return",
    "Weight",
]


st.dataframe(
    display_portfolio,
    width="stretch",
    hide_index=True,
)