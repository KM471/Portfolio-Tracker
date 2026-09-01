from pathlib import Path

import pandas as pd
import streamlit as st


st.set_page_config(
    page_title="Portfolio Intelligence",
    page_icon="📊",
    layout="wide",
)

st.title("Portfolio Intelligence")
st.caption("Portfolio overview")

data_path = Path("data/sample_portfolio.csv")

portfolio = pd.read_csv(data_path)

portfolio["market_value"] = portfolio["shares"] * portfolio["price"]

total_value = portfolio["market_value"].sum()

portfolio["weight"] = portfolio["market_value"] / total_value

largest_position = portfolio.loc[portfolio["market_value"].idxmax()]

col1, col2, col3 = st.columns(3)

col1.metric(
    label="Total Portfolio Value",
    value=f"${total_value:,.2f}",
)

col2.metric(
    label="Number of Holdings",
    value=len(portfolio),
)

col3.metric(
    label="Largest Position",
    value=largest_position["ticker"],
    delta=f"{largest_position['weight']:.1%} of portfolio",
)

st.subheader("Holdings")

display_portfolio = portfolio.copy()

display_portfolio["price"] = display_portfolio["price"].map(
    lambda value: f"${value:,.2f}"
)

display_portfolio["market_value"] = display_portfolio["market_value"].map(
    lambda value: f"${value:,.2f}"
)

display_portfolio["weight"] = display_portfolio["weight"].map(
    lambda value: f"{value:.2%}"
)

st.dataframe(
    display_portfolio,
    width="stretch",
    hide_index=True,
)