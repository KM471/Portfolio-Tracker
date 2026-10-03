import pandas as pd

from history_cache import (
    get_cached_transactions,
    get_cached_orders,
    get_cached_dividends,
)
from portfolio_history import get_portfolio_history


SECONDS_PER_DAY = 24 * 60 * 60


def _normalise_datetime(series):
    return pd.to_datetime(
        series,
        utc=True,
        errors="coerce",
    )


def _normalise_date(series):
    return (
        _normalise_datetime(series)
        .dt.tz_convert(None)
        .dt.normalize()
    )


# ============================================================
# TRANSACTION CASH FLOWS
# ============================================================

def _prepare_transactions(force_refresh=False):
    transactions = (
        get_cached_transactions(
            force_refresh=force_refresh,
        )
        .copy()
    )

    empty = pd.DataFrame(
        columns=[
            "date",
            "external_flow_eur",
            "weighted_external_flow_eur",
            "internal_cash_flow_eur",
        ]
    )

    if transactions.empty:
        return empty

    transactions["timestamp"] = _normalise_datetime(
        transactions["dateTime"]
    )

    transactions["date"] = (
        transactions["timestamp"]
        .dt.tz_convert(None)
        .dt.normalize()
    )

    transactions["amount"] = pd.to_numeric(
        transactions["amount"],
        errors="coerce",
    )

    transactions["type"] = (
        transactions["type"]
        .astype(str)
        .str.upper()
    )

    transactions = transactions.dropna(
        subset=[
            "timestamp",
            "date",
            "amount",
        ]
    )

    if transactions.empty:
        return empty

    # --------------------------------------------------------
    # External investor cash flows
    # --------------------------------------------------------
    #
    # Only money entering or leaving the brokerage account
    # changes investor-contributed capital.
    #
    # DEPOSIT:
    #     positive account cash flow
    #
    # WITHDRAW:
    #     negative account cash flow
    #
    # These are the only transaction types that should also
    # influence the cash-flow-matched benchmark and be
    # neutralised when calculating portfolio TWR.
    # --------------------------------------------------------

    transactions["external_flow_eur"] = 0.0

    deposit_mask = (
        transactions["type"] == "DEPOSIT"
    )

    withdrawal_mask = (
        transactions["type"] == "WITHDRAW"
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
        withdrawal_mask,
        "external_flow_eur",
    ] = -(
        transactions.loc[
            withdrawal_mask,
            "amount",
        ]
        .abs()
    )

    # --------------------------------------------------------
    # Internal account cash flows
    # --------------------------------------------------------
    #
    # These change brokerage cash and therefore total account
    # NAV, but they are NOT investor contributions/withdrawals.
    #
    # INTEREST_ON_FREE_CASH:
    #     account income -> increases cash / NAV
    #
    # FEE:
    #     account expense -> reduces cash / NAV
    #
    # Their original Trading 212 amount sign is retained.
    # --------------------------------------------------------

    transactions["internal_cash_flow_eur"] = 0.0

    internal_cash_mask = (
        transactions["type"].isin(
            [
                "INTEREST_ON_FREE_CASH",
                "FEE",
            ]
        )
    )

    transactions.loc[
        internal_cash_mask,
        "internal_cash_flow_eur",
    ] = transactions.loc[
        internal_cash_mask,
        "amount",
    ]

    # --------------------------------------------------------
    # Modified-Dietz external-flow timing
    # --------------------------------------------------------
    #
    # A deposit/withdrawal near the start of the day receives
    # a weight near 1.
    #
    # A deposit/withdrawal near the end of the day receives
    # a weight near 0.
    #
    # Internal account income/expenses are NOT included here
    # because they are part of portfolio performance rather
    # than investor cash flows.
    # --------------------------------------------------------

    utc_midnight = (
        transactions["timestamp"]
        .dt.normalize()
    )

    seconds_into_day = (
        transactions["timestamp"]
        - utc_midnight
    ).dt.total_seconds()

    transactions["flow_weight"] = (
        1.0
        - (
            seconds_into_day
            / SECONDS_PER_DAY
        )
    ).clip(
        lower=0.0,
        upper=1.0,
    )

    transactions[
        "weighted_external_flow_eur"
    ] = (
        transactions["external_flow_eur"]
        * transactions["flow_weight"]
    )

    return transactions[
        [
            "date",
            "external_flow_eur",
            "weighted_external_flow_eur",
            "internal_cash_flow_eur",
        ]
    ]


# ============================================================
# TRADE CASH MOVEMENTS
# ============================================================

def _prepare_orders(force_refresh=False):
    orders = (
        get_cached_orders(
            force_refresh=force_refresh,
        )
        .copy()
    )

    empty = pd.DataFrame(
        columns=[
            "date",
            "trade_cash_flow_eur",
            "trade_taxes_eur",
        ]
    )

    if orders.empty:
        return empty

    orders = orders[
        (orders["status"] == "FILLED")
        & orders["side"].isin(
            ["BUY", "SELL"]
        )
    ].copy()

    if orders.empty:
        return empty

    orders["date"] = _normalise_date(
        orders["filled_at"]
    )

    orders["net_value"] = pd.to_numeric(
        orders["net_value"],
        errors="coerce",
    ).fillna(0.0)

    orders["taxes"] = pd.to_numeric(
        orders["taxes"],
        errors="coerce",
    ).fillna(0.0)

    orders["trade_cash_flow_eur"] = 0.0

    buy_mask = orders["side"] == "BUY"
    sell_mask = orders["side"] == "SELL"

    # walletImpact.netValue is the account-wallet impact.
    #
    # BUY:
    #     securities increase, brokerage cash decreases
    #
    # SELL:
    #     securities decrease, brokerage cash increases
    #
    # These are internal reallocations and are therefore NOT
    # external investor cash flows.
    orders.loc[
        buy_mask,
        "trade_cash_flow_eur",
    ] = -orders.loc[
        buy_mask,
        "net_value",
    ].abs()

    orders.loc[
        sell_mask,
        "trade_cash_flow_eur",
    ] = orders.loc[
        sell_mask,
        "net_value",
    ].abs()

    # Taxes are retained for analytics only.
    #
    # They are not subtracted again here because Trading 212's
    # walletImpact.netValue already incorporates the wallet
    # effect of the trade.
    orders["trade_taxes_eur"] = orders["taxes"]

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

def _prepare_dividends(force_refresh=False):
    dividends = (
        get_cached_dividends(
            force_refresh=force_refresh,
        )
        .copy()
    )

    empty = pd.DataFrame(
        columns=[
            "date",
            "dividend_cash_eur",
        ]
    )

    if dividends.empty:
        return empty

    dividends["date"] = _normalise_date(
        dividends["paidOn"]
    )

    dividends["dividend_cash_eur"] = (
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

def get_account_history(force_refresh=False):
    portfolio, _ = get_portfolio_history(
        force_refresh=force_refresh,
    )

    transactions = _prepare_transactions(
        force_refresh=force_refresh,
    )

    orders = _prepare_orders(
        force_refresh=force_refresh,
    )

    dividends = _prepare_dividends(
        force_refresh=force_refresh,
    )

    date_candidates = []

    if not portfolio.empty:
        portfolio = portfolio.copy()

        portfolio["date"] = pd.to_datetime(
            portfolio["date"],
            errors="coerce",
        ).dt.normalize()

        portfolio = portfolio.dropna(
            subset=["date"]
        )

        if not portfolio.empty:
            date_candidates.extend(
                [
                    portfolio["date"].min(),
                    portfolio["date"].max(),
                ]
            )

    for frame in (
        transactions,
        orders,
        dividends,
    ):
        if not frame.empty:
            date_candidates.extend(
                [
                    frame["date"].min(),
                    frame["date"].max(),
                ]
            )

    date_candidates = [
        pd.Timestamp(value).normalize()
        for value in date_candidates
        if pd.notna(value)
    ]

    if not date_candidates:
        raise ValueError(
            "No historical portfolio or cash activity was found."
        )

    first_date = min(
        date_candidates
    )

    if not portfolio.empty:
        last_date = max(
            portfolio["date"].max(),
            max(date_candidates),
        )

    else:
        last_date = max(
            max(date_candidates),
            pd.Timestamp.now(
                tz="UTC"
            )
            .tz_convert(None)
            .normalize(),
        )

    calendar = pd.DataFrame(
        {
            "date": pd.date_range(
                first_date,
                last_date,
                freq="D",
            )
        }
    )

    # --------------------------------------------------------
    # Holdings value
    # --------------------------------------------------------

    if portfolio.empty:
        history = calendar.copy()

        history["invested_value_eur"] = 0.0
        history["open_positions"] = 0
        history["missing_positions"] = 0
        history["trade_count"] = 0
        history["gross_buys_eur"] = 0.0
        history["gross_sells_eur"] = 0.0
        history["net_trade_flow_eur"] = 0.0

    else:
        history = calendar.merge(
            portfolio,
            on="date",
            how="left",
        )

        portfolio_first_date = (
            portfolio["date"].min()
        )

        portfolio_last_date = (
            portfolio["date"].max()
        )

        history["invested_value_eur"] = pd.to_numeric(
            history["invested_value_eur"],
            errors="coerce",
        )

        # Before the first trade, holdings are genuinely zero.
        history.loc[
            history["date"] < portfolio_first_date,
            "invested_value_eur",
        ] = 0.0

        # Only dates AFTER the latest market observation may
        # carry the last known valuation forward.
        #
        # Missing values inside the portfolio-history range stay
        # missing so incomplete market valuation cannot silently
        # create a fake return.
        last_known_invested = (
            portfolio
            .sort_values("date")[
                "invested_value_eur"
            ]
            .dropna()
        )

        if not last_known_invested.empty:
            history.loc[
                history["date"] > portfolio_last_date,
                "invested_value_eur",
            ] = float(
                last_known_invested.iloc[-1]
            )

        for column in (
            "open_positions",
            "missing_positions",
        ):
            history[column] = pd.to_numeric(
                history[column],
                errors="coerce",
            )

            history.loc[
                history["date"] < portfolio_first_date,
                column,
            ] = 0

            last_known = (
                portfolio
                .sort_values("date")[column]
                .dropna()
            )

            if not last_known.empty:
                history.loc[
                    history["date"] > portfolio_last_date,
                    column,
                ] = last_known.iloc[-1]

            history[column] = (
                history[column]
                .fillna(0)
                .astype(int)
            )

        for column in (
            "trade_count",
            "gross_buys_eur",
            "gross_sells_eur",
            "net_trade_flow_eur",
        ):
            history[column] = (
                pd.to_numeric(
                    history[column],
                    errors="coerce",
                )
                .fillna(0.0)
            )

    # --------------------------------------------------------
    # Daily transaction activity
    # --------------------------------------------------------

    if transactions.empty:
        transaction_daily = pd.DataFrame(
            columns=[
                "date",
                "external_flow_eur",
                "weighted_external_flow_eur",
                "internal_cash_flow_eur",
            ]
        )

    else:
        transaction_daily = (
            transactions
            .groupby(
                "date",
                as_index=False,
            )[
                [
                    "external_flow_eur",
                    "weighted_external_flow_eur",
                    "internal_cash_flow_eur",
                ]
            ]
            .sum()
        )

    # --------------------------------------------------------
    # Daily trade activity
    # --------------------------------------------------------

    if orders.empty:
        order_daily = pd.DataFrame(
            columns=[
                "date",
                "trade_cash_flow_eur",
                "trade_taxes_eur",
            ]
        )

    else:
        order_daily = (
            orders
            .groupby(
                "date",
                as_index=False,
            )[
                [
                    "trade_cash_flow_eur",
                    "trade_taxes_eur",
                ]
            ]
            .sum()
        )

    # --------------------------------------------------------
    # Daily dividend activity
    # --------------------------------------------------------

    if dividends.empty:
        dividend_daily = pd.DataFrame(
            columns=[
                "date",
                "dividend_cash_eur",
            ]
        )

    else:
        dividend_daily = (
            dividends
            .groupby(
                "date",
                as_index=False,
            )[
                "dividend_cash_eur"
            ]
            .sum()
        )

    # --------------------------------------------------------
    # Merge all account cash activity
    # --------------------------------------------------------

    history = history.merge(
        transaction_daily,
        on="date",
        how="left",
    )

    history = history.merge(
        order_daily,
        on="date",
        how="left",
    )

    history = history.merge(
        dividend_daily,
        on="date",
        how="left",
    )

    cash_columns = [
        "external_flow_eur",
        "weighted_external_flow_eur",
        "internal_cash_flow_eur",
        "trade_cash_flow_eur",
        "trade_taxes_eur",
        "dividend_cash_eur",
    ]

    history[cash_columns] = (
        history[cash_columns]
        .apply(
            pd.to_numeric,
            errors="coerce",
        )
        .fillna(0.0)
    )

    # --------------------------------------------------------
    # Cash balance
    # --------------------------------------------------------
    #
    # Brokerage cash changes due to:
    #
    # 1. investor deposits / withdrawals
    # 2. internal account income / expenses
    # 3. stock purchases / sales
    # 4. dividends
    #
    # Buying or selling securities changes the split between
    # securities and cash but should not mechanically change NAV.
    # --------------------------------------------------------

    history["daily_cash_change_eur"] = (
        history["external_flow_eur"]
        + history["internal_cash_flow_eur"]
        + history["trade_cash_flow_eur"]
        + history["dividend_cash_eur"]
    )

    history["cash_balance_eur"] = (
        history[
            "daily_cash_change_eur"
        ]
        .cumsum()
    )

    # --------------------------------------------------------
    # Total account NAV
    # --------------------------------------------------------
    #
    # NAV = securities market value + brokerage cash
    # --------------------------------------------------------

    history["account_value_eur"] = (
        history["invested_value_eur"]
        + history["cash_balance_eur"]
    )

    # --------------------------------------------------------
    # Net investor capital
    # --------------------------------------------------------
    #
    # Only deposits and withdrawals change contributed capital.
    #
    # Interest, fees, dividends and trading activity are part of
    # the account's investment result rather than investor
    # contributions.
    # --------------------------------------------------------

    history["net_capital_invested_eur"] = (
        history[
            "external_flow_eur"
        ]
        .cumsum()
    )

    history["cumulative_taxes_eur"] = (
        history[
            "trade_taxes_eur"
        ]
        .cumsum()
    )

    return (
        history
        .sort_values("date")
        .reset_index(drop=True)
    )