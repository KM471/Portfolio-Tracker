import pandas as pd

from history_cache import (
    get_cached_transactions,
    get_cached_orders,
    get_cached_dividends,
)

from portfolio_history import get_portfolio_history


def _normalise_date(series):

    return (
        pd.to_datetime(
            series,
            utc=True,
            errors="coerce",
        )
        .dt.tz_convert(None)
        .dt.normalize()
    )


# ============================================================
# EXTERNAL CASH FLOWS
# ============================================================

def _prepare_transactions():

    transactions = (
        get_cached_transactions()
        .copy()
    )

    if transactions.empty:

        return pd.DataFrame(
            columns=[
                "date",
                "external_flow_eur",
            ]
        )

    transactions["date"] = (
        _normalise_date(
            transactions["dateTime"]
        )
    )

    transactions["amount"] = (
        pd.to_numeric(
            transactions["amount"],
            errors="coerce",
        )
    )

    transactions["type"] = (
        transactions["type"]
        .astype(str)
        .str.upper()
    )

    transactions = transactions[
        transactions["type"].isin(
            [
                "DEPOSIT",
                "WITHDRAW",
            ]
        )
    ].copy()

    transactions[
        "external_flow_eur"
    ] = 0.0

    deposit_mask = (
        transactions["type"]
        == "DEPOSIT"
    )

    withdraw_mask = (
        transactions["type"]
        == "WITHDRAW"
    )

    transactions.loc[
        deposit_mask,
        "external_flow_eur",
    ] = (
        transactions.loc[
            deposit_mask,
            "amount",
        ]
        .abs()
    )

    transactions.loc[
        withdraw_mask,
        "external_flow_eur",
    ] = (
        -transactions.loc[
            withdraw_mask,
            "amount",
        ]
        .abs()
    )

    return transactions[
        [
            "date",
            "external_flow_eur",
        ]
    ].dropna()


# ============================================================
# TRADE CASH MOVEMENTS
#
# net_value represents the wallet impact of the trade.
#
# IMPORTANT:
# Trading 212 net_value already incorporates trade taxes.
# Therefore taxes must NOT be applied to cash a second time.
# ============================================================

def _prepare_orders():

    orders = (
        get_cached_orders()
        .copy()
    )

    if orders.empty:

        return pd.DataFrame(
            columns=[
                "date",
                "trade_cash_flow_eur",
                "trade_taxes_eur",
            ]
        )

    orders = orders[
        (
            orders["status"]
            == "FILLED"
        )
        &
        (
            orders["side"].isin(
                [
                    "BUY",
                    "SELL",
                ]
            )
        )
    ].copy()

    orders["date"] = (
        _normalise_date(
            orders["filled_at"]
        )
    )

    orders["net_value"] = (
        pd.to_numeric(
            orders["net_value"],
            errors="coerce",
        )
        .fillna(0.0)
    )

    orders["taxes"] = (
        pd.to_numeric(
            orders["taxes"],
            errors="coerce",
        )
        .fillna(0.0)
    )

    orders[
        "trade_cash_flow_eur"
    ] = 0.0

    buy_mask = (
        orders["side"]
        == "BUY"
    )

    sell_mask = (
        orders["side"]
        == "SELL"
    )

    orders.loc[
        buy_mask,
        "trade_cash_flow_eur",
    ] = (
        -orders.loc[
            buy_mask,
            "net_value",
        ]
        .abs()
    )

    orders.loc[
        sell_mask,
        "trade_cash_flow_eur",
    ] = (
        orders.loc[
            sell_mask,
            "net_value",
        ]
        .abs()
    )

    # Keep taxes for later analytics,
    # but DO NOT add them separately to cash.
    orders[
        "trade_taxes_eur"
    ] = orders["taxes"]

    return orders[
        [
            "date",
            "trade_cash_flow_eur",
            "trade_taxes_eur",
        ]
    ].dropna(
        subset=["date"]
    )


# ============================================================
# DIVIDENDS
# ============================================================

def _prepare_dividends():

    dividends = (
        get_cached_dividends()
        .copy()
    )

    if dividends.empty:

        return pd.DataFrame(
            columns=[
                "date",
                "dividend_cash_eur",
            ]
        )

    dividends["date"] = (
        _normalise_date(
            dividends["paidOn"]
        )
    )

    dividends[
        "dividend_cash_eur"
    ] = (
        pd.to_numeric(
            dividends["amountInEuro"],
            errors="coerce",
        )
        .fillna(0.0)
    )

    return dividends[
        [
            "date",
            "dividend_cash_eur",
        ]
    ].dropna(
        subset=["date"]
    )


# ============================================================
# BUILD HISTORICAL ACCOUNT VALUE
# ============================================================

def get_account_history(
    force_refresh=False,
):

    portfolio, _ = (
        get_portfolio_history(
            force_refresh=force_refresh,
        )
    )

    if portfolio.empty:

        raise ValueError(
            "Portfolio history is empty."
        )

    portfolio = portfolio.copy()

    portfolio["date"] = (
        pd.to_datetime(
            portfolio["date"],
            errors="coerce",
        )
        .dt.normalize()
    )

    portfolio = (
        portfolio
        .sort_values("date")
        .reset_index(drop=True)
    )

    transactions = (
        _prepare_transactions()
    )

    orders = (
        _prepare_orders()
    )

    dividends = (
        _prepare_dividends()
    )

    # ========================================================
    # DAILY TOTALS
    # ========================================================

    external_daily = (
        transactions
        .groupby("date")[
            "external_flow_eur"
        ]
        .sum()
    )

    order_daily = (
        orders
        .groupby("date")[
            [
                "trade_cash_flow_eur",
                "trade_taxes_eur",
            ]
        ]
        .sum()
    )

    dividend_daily = (
        dividends
        .groupby("date")[
            "dividend_cash_eur"
        ]
        .sum()
    )

    # ========================================================
    # MERGE
    # ========================================================

    history = portfolio.copy()

    history = history.merge(
        external_daily.rename(
            "external_flow_eur"
        ),
        left_on="date",
        right_index=True,
        how="left",
    )

    history = history.merge(
        order_daily,
        left_on="date",
        right_index=True,
        how="left",
    )

    history = history.merge(
        dividend_daily.rename(
            "dividend_cash_eur"
        ),
        left_on="date",
        right_index=True,
        how="left",
    )

    columns = [
        "external_flow_eur",
        "trade_cash_flow_eur",
        "trade_taxes_eur",
        "dividend_cash_eur",
    ]

    history[
        columns
    ] = (
        history[
            columns
        ]
        .fillna(0.0)
    )

    # ========================================================
    # CASH BALANCE
    #
    # Taxes are NOT separately added here.
    #
    # They are already contained inside trade net_value.
    # ========================================================

    history[
        "daily_cash_change_eur"
    ] = (
        history[
            "external_flow_eur"
        ]
        +
        history[
            "trade_cash_flow_eur"
        ]
        +
        history[
            "dividend_cash_eur"
        ]
    )

    history[
        "cash_balance_eur"
    ] = (
        history[
            "daily_cash_change_eur"
        ]
        .cumsum()
    )

    # ========================================================
    # TOTAL ACCOUNT VALUE
    # ========================================================

    history[
        "account_value_eur"
    ] = (
        history[
            "invested_value_eur"
        ]
        +
        history[
            "cash_balance_eur"
        ]
    )

    # ========================================================
    # NET EXTERNAL CAPITAL
    # ========================================================

    history[
        "net_capital_invested_eur"
    ] = (
        history[
            "external_flow_eur"
        ]
        .cumsum()
    )

    # ========================================================
    # CUMULATIVE TAXES
    #
    # Useful later for dashboard analytics.
    # ========================================================

    history[
        "cumulative_taxes_eur"
    ] = (
        history[
            "trade_taxes_eur"
        ]
        .cumsum()
    )

    return history