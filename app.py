import streamlit as st

from trading212 import get_account_summary, get_positions


st.set_page_config(
    page_title="Portfolio Intelligence",
    page_icon="📊",
    layout="wide",
)

st.title("Portfolio Intelligence")
st.caption("Live portfolio data from Trading 212")


try:
    account = get_account_summary()
    portfolio = get_positions()

except Exception as error:
    st.error("Could not load Trading 212 data.")
    st.exception(error)
    st.stop()


currency = account["currency"]
currency_symbol = "€" if currency == "EUR" else currency

total_value = account["totalValue"]

cash_available = account["cash"]["availableToTrade"]

investment_value = account["investments"]["currentValue"]
investment_cost = account["investments"]["totalCost"]
total_unrealised_pnl = account["investments"]["unrealizedProfitLoss"]


if investment_value > 0:
    portfolio["weight"] = portfolio["current_value"] / investment_value
else:
    portfolio["weight"] = 0


largest_position = portfolio.loc[portfolio["current_value"].idxmax()]


col1, col2, col3, col4 = st.columns(4)

col1.metric(
    label="Total Account Value",
    value=f"{currency_symbol}{total_value:,.2f}",
)

col2.metric(
    label="Investments",
    value=f"{currency_symbol}{investment_value:,.2f}",
)

col3.metric(
    label="Available Cash",
    value=f"{currency_symbol}{cash_available:,.2f}",
)

col4.metric(
    label="Unrealised P/L",
    value=f"{currency_symbol}{total_unrealised_pnl:,.2f}",
)


st.divider()


col5, col6, col7 = st.columns(3)

col5.metric(
    label="Open Positions",
    value=len(portfolio),
)

col6.metric(
    label="Investment Cost",
    value=f"{currency_symbol}{investment_cost:,.2f}",
)

col7.metric(
    label="Largest Position",
    value=largest_position["ticker"],
    delta=f"{largest_position['weight']:.1%} of investments",
)


st.subheader("Current Holdings")


display_portfolio = portfolio[
    [
        "ticker",
        "company",
        "quantity",
        "average_price",
        "current_price",
        "total_cost",
        "current_value",
        "unrealised_pnl",
        "weight",
    ]
].copy()


display_portfolio["average_price"] = display_portfolio["average_price"].map(
    lambda value: f"{value:,.2f}"
)

display_portfolio["current_price"] = display_portfolio["current_price"].map(
    lambda value: f"{value:,.2f}"
)

display_portfolio["total_cost"] = display_portfolio["total_cost"].map(
    lambda value: f"{currency_symbol}{value:,.2f}"
)

display_portfolio["current_value"] = display_portfolio["current_value"].map(
    lambda value: f"{currency_symbol}{value:,.2f}"
)

display_portfolio["unrealised_pnl"] = display_portfolio["unrealised_pnl"].map(
    lambda value: f"{currency_symbol}{value:,.2f}"
)

display_portfolio["weight"] = display_portfolio["weight"].map(
    lambda value: f"{value:.2%}"
)


display_portfolio.columns = [
    "Ticker",
    "Company",
    "Quantity",
    "Average Price",
    "Current Price",
    "Cost",
    "Current Value",
    "Unrealised P/L",
    "Weight",
]


st.dataframe(
    display_portfolio,
    width="stretch",
    hide_index=True,
)