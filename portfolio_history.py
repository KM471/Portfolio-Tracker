import pandas as pd

from history_cache import get_cached_orders
from market_data import get_all_price_history
from fx_data import get_all_fx_history


# ============================================================
# ORDER DATA
# ============================================================

def _prepare_orders():
    orders = get_cached_orders().copy()

    orders = orders[
        (orders["status"] == "FILLED")
        & (orders["side"].isin(["BUY", "SELL"]))
    ].copy()

    orders["filled_at"] = pd.to_datetime(
        orders["filled_at"],
        utc=True,
        errors="coerce",
    )

    orders["trade_date"] = (
        orders["filled_at"]
        .dt.tz_convert(None)
        .dt.normalize()
    )

    orders["quantity"] = pd.to_numeric(
        orders["quantity"],
        errors="coerce",
    )

    orders["filled_value"] = pd.to_numeric(
        orders["filled_value"],
        errors="coerce",
    )

    orders["net_value"] = pd.to_numeric(
        orders["net_value"],
        errors="coerce",
    )

    orders["trade_value_eur"] = (
        orders["filled_value"]
        .fillna(
            orders["net_value"]
        )
        .abs()
    )

    orders["quantity"] = (
        orders["quantity"]
        .abs()
    )

    orders = orders.dropna(
        subset=[
            "trade_date",
            "ticker",
            "quantity",
        ]
    )

    missing_trade_values = (
        orders[
            "trade_value_eur"
        ]
        .isna()
        .sum()
    )

    if missing_trade_values > 0:
        raise ValueError(
            f"{missing_trade_values} trades have no usable "
            f"filled_value or net_value."
        )

    orders = orders.sort_values(
        [
            "trade_date",
            "filled_at",
        ]
    ).reset_index(drop=True)

    return orders


# ============================================================
# MARKET PRICE DATA
# ============================================================

def _prepare_price_data(
    tickers,
    start_date,
    force_refresh=False,
):
    prices = get_all_price_history(
        tickers,
        start_date=start_date,
        force_refresh=force_refresh,
    ).copy()

    prices["date"] = pd.to_datetime(
        prices["date"],
        errors="coerce",
    ).dt.normalize()

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

    prices = prices.drop_duplicates(
        subset=[
            "trading212_ticker",
            "date",
        ],
        keep="last",
    )

    return prices


# ============================================================
# FX DATA
# ============================================================

def _prepare_fx_data(
    currencies,
    start_date,
    force_refresh=False,
):
    fx = get_all_fx_history(
        currencies,
        start_date=start_date,
        force_refresh=force_refresh,
    ).copy()

    fx["date"] = pd.to_datetime(
        fx["date"],
        errors="coerce",
    ).dt.normalize()

    fx["rate_to_eur"] = pd.to_numeric(
        fx["rate_to_eur"],
        errors="coerce",
    )

    fx = fx.dropna(
        subset=[
            "date",
            "currency",
            "rate_to_eur",
        ]
    )

    fx = fx.sort_values(
        [
            "currency",
            "date",
        ]
    )

    fx = fx.drop_duplicates(
        subset=[
            "currency",
            "date",
        ],
        keep="last",
    )

    return fx


# ============================================================
# PORTFOLIO HISTORY
# ============================================================

def get_portfolio_history(
    force_refresh=False,
):
    orders = _prepare_orders()

    if orders.empty:
        return (
            pd.DataFrame(),
            pd.DataFrame(),
        )

    tickers = sorted(
        orders[
            "ticker"
        ]
        .dropna()
        .unique()
        .tolist()
    )

    first_trade_date = (
        orders[
            "trade_date"
        ]
        .min()
        .normalize()
    )

    start_date_text = (
        first_trade_date
        .strftime("%Y-%m-%d")
    )

    prices = _prepare_price_data(
        tickers,
        start_date_text,
        force_refresh=force_refresh,
    )

    currency_map = (
        prices[
            [
                "trading212_ticker",
                "currency",
            ]
        ]
        .drop_duplicates(
            subset=[
                "trading212_ticker",
            ]
        )
        .set_index(
            "trading212_ticker"
        )["currency"]
        .to_dict()
    )

    currencies = sorted(
        set(
            currency_map.values()
        )
    )

    fx = _prepare_fx_data(
        currencies,
        start_date_text,
        force_refresh=force_refresh,
    )

    last_price_date = (
        prices[
            "date"
        ]
        .max()
        .normalize()
    )

    calendar = pd.date_range(
        start=first_trade_date,
        end=last_price_date,
        freq="D",
    )

    price_table = (
        prices.pivot(
            index="date",
            columns="trading212_ticker",
            values="close",
        )
        .reindex(
            calendar
        )
        .ffill()
    )

    fx_table = (
        fx.pivot(
            index="date",
            columns="currency",
            values="rate_to_eur",
        )
        .reindex(
            calendar
        )
        .ffill()
        .bfill()
    )

    orders_by_date = {
        date: group
        for date, group
        in orders.groupby(
            "trade_date"
        )
    }

    quantities = {
        ticker: 0.0
        for ticker in tickers
    }

    daily_records = []

    holding_records = []

    for date in calendar:

        day_orders = (
            orders_by_date.get(
                date
            )
        )

        gross_buys_eur = 0.0
        gross_sells_eur = 0.0
        trade_count = 0

        if day_orders is not None:

            for _, order in (
                day_orders.iterrows()
            ):

                ticker = (
                    order[
                        "ticker"
                    ]
                )

                quantity = float(
                    order[
                        "quantity"
                    ]
                )

                trade_value = float(
                    order[
                        "trade_value_eur"
                    ]
                )

                side = (
                    order[
                        "side"
                    ]
                )

                if side == "BUY":

                    quantities[
                        ticker
                    ] += quantity

                    gross_buys_eur += (
                        trade_value
                    )

                elif side == "SELL":

                    quantities[
                        ticker
                    ] -= quantity

                    gross_sells_eur += (
                        trade_value
                    )

                trade_count += 1

        for ticker in tickers:

            if abs(
                quantities[
                    ticker
                ]
            ) < 1e-8:

                quantities[
                    ticker
                ] = 0.0

        invested_value_eur = 0.0
        open_positions = 0
        missing_positions = 0

        for ticker in tickers:

            quantity = (
                quantities[
                    ticker
                ]
            )

            if quantity <= 0:
                continue

            open_positions += 1

            if (
                ticker
                not in price_table.columns
            ):
                missing_positions += 1
                continue

            price = (
                price_table.at[
                    date,
                    ticker,
                ]
            )

            currency = (
                currency_map.get(
                    ticker
                )
            )

            if (
                currency is None
                or currency
                not in fx_table.columns
            ):
                missing_positions += 1
                continue

            fx_rate = (
                fx_table.at[
                    date,
                    currency,
                ]
            )

            if (
                pd.isna(
                    price
                )
                or pd.isna(
                    fx_rate
                )
            ):
                missing_positions += 1
                continue

            price = float(
                price
            )

            fx_rate = float(
                fx_rate
            )

            value_eur = (
                quantity
                * price
                * fx_rate
            )

            invested_value_eur += (
                value_eur
            )

            holding_records.append(
                {
                    "date": date,
                    "ticker": ticker,
                    "quantity": quantity,
                    "price": price,
                    "currency": currency,
                    "fx_rate_to_eur": (
                        fx_rate
                    ),
                    "value_eur": (
                        value_eur
                    ),
                }
            )

        net_trade_flow_eur = (
            gross_buys_eur
            - gross_sells_eur
        )

        daily_records.append(
            {
                "date": date,

                "invested_value_eur": (
                    invested_value_eur
                ),

                "open_positions": (
                    open_positions
                ),

                "missing_positions": (
                    missing_positions
                ),

                "trade_count": (
                    trade_count
                ),

                "gross_buys_eur": (
                    gross_buys_eur
                ),

                "gross_sells_eur": (
                    gross_sells_eur
                ),

                "net_trade_flow_eur": (
                    net_trade_flow_eur
                ),
            }
        )

    portfolio_history = pd.DataFrame(
        daily_records
    )

    holdings_history = pd.DataFrame(
        holding_records
    )

    return (
        portfolio_history,
        holdings_history,
    )