import numpy as np
import pandas as pd

from history_cache import get_cached_orders
from market_data import get_all_price_history
from fx_data import get_all_fx_history


QUANTITY_ZERO_TOLERANCE = 1e-8


# ============================================================
# ORDER DATA
# ============================================================

def _prepare_orders(force_refresh=False):
    orders = (
        get_cached_orders(
            force_refresh=force_refresh,
        )
        .copy()
    )

    if orders.empty:
        return orders

    orders = orders[
        (orders["status"] == "FILLED")
        & orders["side"].isin(
            ["BUY", "SELL"]
        )
    ].copy()

    if orders.empty:
        return orders

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
    ).abs()

    orders["net_value"] = pd.to_numeric(
        orders["net_value"],
        errors="coerce",
    )

    # walletImpact.netValue is the actual account-currency
    # wallet movement caused by the trade.
    orders["trade_value_eur"] = (
        orders["net_value"]
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
            "walletImpact.netValue."
        )

    return (
        orders
        .sort_values(
            [
                "trade_date",
                "filled_at",
            ]
        )
        .reset_index(
            drop=True
        )
    )


# ============================================================
# MARKET PRICE DATA
# ============================================================

def _prepare_price_data(
    tickers,
    start_date,
    force_refresh=False,
):
    prices = (
        get_all_price_history(
            tickers,
            start_date=start_date,
            force_refresh=force_refresh,
        )
        .copy()
    )

    prices["date"] = pd.to_datetime(
        prices["date"],
        errors="coerce",
    ).dt.normalize()

    prices["close"] = pd.to_numeric(
        prices["close"],
        errors="coerce",
    )

    # Yahoo supplies stock-split events alongside its historical
    # prices. The price history itself is already represented on
    # the split-adjusted share basis, so historical Trading 212
    # order quantities must be converted to that same basis.
    if (
        "stock_splits"
        not in prices.columns
    ):
        prices[
            "stock_splits"
        ] = 0.0

    prices[
        "stock_splits"
    ] = (
        pd.to_numeric(
            prices[
                "stock_splits"
            ],
            errors="coerce",
        )
        .fillna(0.0)
    )

    prices = prices.dropna(
        subset=[
            "date",
            "trading212_ticker",
            "close",
        ]
    )

    return (
        prices
        .sort_values(
            [
                "trading212_ticker",
                "date",
            ]
        )
        .drop_duplicates(
            subset=[
                "trading212_ticker",
                "date",
            ],
            keep="last",
        )
        .reset_index(
            drop=True
        )
    )


# ============================================================
# STOCK-SPLIT ADJUSTMENT
# ============================================================

def _build_split_events(
    prices,
):
    """
    Return known Yahoo split events for each Trading 212 ticker.

    Yahoo's historical price series is represented on today's
    split-adjusted share basis.

    Trading 212 historical orders, however, contain the quantity
    that actually existed at the time of each trade.

    Therefore an order before a later split must have its
    historical quantity multiplied by that future split ratio
    before it can be combined with Yahoo's adjusted price series.
    """

    if (
        prices.empty
        or "stock_splits"
        not in prices.columns
    ):
        return {}

    split_rows = prices[
        (
            prices[
                "stock_splits"
            ].notna()
        )
        & (
            prices[
                "stock_splits"
            ] > 0
        )
        & (
            ~np.isclose(
                prices[
                    "stock_splits"
                ],
                1.0,
            )
        )
    ][
        [
            "trading212_ticker",
            "date",
            "stock_splits",
        ]
    ].copy()

    if split_rows.empty:
        return {}

    split_events = {}

    for (
        ticker,
        group,
    ) in split_rows.groupby(
        "trading212_ticker"
    ):
        events = []

        for _, row in (
            group
            .sort_values("date")
            .iterrows()
        ):
            split_ratio = float(
                row[
                    "stock_splits"
                ]
            )

            if (
                not np.isfinite(
                    split_ratio
                )
                or split_ratio <= 0
            ):
                continue

            events.append(
                (
                    pd.Timestamp(
                        row["date"]
                    ).normalize(),
                    split_ratio,
                )
            )

        if events:
            split_events[
                ticker
            ] = events

    return split_events


def _split_adjustment_factor(
    ticker,
    trade_date,
    split_events,
):
    """
    Convert a historical order quantity onto the share basis used
    by Yahoo's current split-adjusted historical price series.

    Only splits AFTER the trade are applied.

    Example:
        buy 1 share
        later 10-for-1 split
        Yahoo historical price is divided by 10
        adjusted historical quantity becomes 10 shares
    """

    events = split_events.get(
        ticker,
        [],
    )

    if not events:
        return 1.0

    trade_date = (
        pd.Timestamp(
            trade_date
        )
        .normalize()
    )

    factor = 1.0

    for (
        split_date,
        split_ratio,
    ) in events:

        if split_date > trade_date:
            factor *= float(
                split_ratio
            )

    return factor


def _adjust_orders_for_splits(
    orders,
    prices,
):
    """
    Add split-adjusted quantities while retaining the original
    Trading 212 quantities for diagnostics.

    We do NOT alter trade_value_eur. Cash movement always comes
    directly from Trading 212 walletImpact.netValue.
    """

    if orders.empty:
        return orders.copy()

    adjusted = (
        orders.copy()
    )

    adjusted[
        "raw_quantity"
    ] = adjusted[
        "quantity"
    ]

    split_events = (
        _build_split_events(
            prices
        )
    )

    adjustment_factors = []

    for _, order in (
        adjusted.iterrows()
    ):
        factor = (
            _split_adjustment_factor(
                ticker=(
                    order[
                        "ticker"
                    ]
                ),
                trade_date=(
                    order[
                        "trade_date"
                    ]
                ),
                split_events=(
                    split_events
                ),
            )
        )

        adjustment_factors.append(
            factor
        )

    adjusted[
        "split_adjustment_factor"
    ] = adjustment_factors

    adjusted[
        "quantity"
    ] = (
        adjusted[
            "raw_quantity"
        ]
        * adjusted[
            "split_adjustment_factor"
        ]
    )

    return adjusted


# ============================================================
# FX DATA
# ============================================================

def _prepare_fx_data(
    currencies,
    start_date,
    force_refresh=False,
):
    fx = (
        get_all_fx_history(
            currencies,
            start_date=start_date,
            force_refresh=force_refresh,
        )
        .copy()
    )

    fx["date"] = pd.to_datetime(
        fx["date"],
        errors="coerce",
    ).dt.normalize()

    fx["rate_to_eur"] = (
        pd.to_numeric(
            fx[
                "rate_to_eur"
            ],
            errors="coerce",
        )
    )

    fx = fx.dropna(
        subset=[
            "date",
            "currency",
            "rate_to_eur",
        ]
    )

    return (
        fx
        .sort_values(
            [
                "currency",
                "date",
            ]
        )
        .drop_duplicates(
            subset=[
                "currency",
                "date",
            ],
            keep="last",
        )
        .reset_index(
            drop=True
        )
    )


# ============================================================
# PORTFOLIO HISTORY
# ============================================================

def get_portfolio_history(
    force_refresh=False,
):
    raw_orders = _prepare_orders(
        force_refresh=force_refresh,
    )

    if raw_orders.empty:
        return (
            pd.DataFrame(),
            pd.DataFrame(),
        )

    tickers = sorted(
        raw_orders[
            "ticker"
        ]
        .dropna()
        .unique()
        .tolist()
    )

    first_trade_date = (
        raw_orders[
            "trade_date"
        ]
        .min()
        .normalize()
    )

    start_date_text = (
        first_trade_date
        .strftime(
            "%Y-%m-%d"
        )
    )

    prices = _prepare_price_data(
        tickers,
        start_date_text,
        force_refresh=force_refresh,
    )

    if prices.empty:
        raise ValueError(
            "No historical market prices were available "
            "for the traded instruments."
        )

    # Convert historical Trading 212 quantities to the same
    # split-adjusted share basis as Yahoo's historical prices.
    orders = (
        _adjust_orders_for_splits(
            raw_orders,
            prices,
        )
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
                "trading212_ticker"
            ]
        )
        .set_index(
            "trading212_ticker"
        )[
            "currency"
        ]
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
        prices
        .pivot(
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
        fx
        .pivot(
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
        for (
            date,
            group,
        ) in orders.groupby(
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

        # Remove harmless floating-point residue.
        for ticker in tickers:

            if abs(
                quantities[
                    ticker
                ]
            ) < QUANTITY_ZERO_TOLERANCE:

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
                    "date":
                        date,

                    "ticker":
                        ticker,

                    "quantity":
                        quantity,

                    "price":
                        price,

                    "currency":
                        currency,

                    "fx_rate_to_eur":
                        fx_rate,

                    "value_eur":
                        value_eur,
                }
            )

        # A partial portfolio valuation is worse than explicitly
        # reporting that the valuation is unavailable. Otherwise
        # a missing instrument can manufacture a fake return.
        valuation_complete = (
            missing_positions == 0
        )

        if not valuation_complete:
            invested_value_eur = np.nan

        daily_records.append(
            {
                "date":
                    date,

                "invested_value_eur":
                    invested_value_eur,

                "valuation_complete":
                    valuation_complete,

                "open_positions":
                    open_positions,

                "missing_positions":
                    missing_positions,

                "trade_count":
                    trade_count,

                "gross_buys_eur":
                    gross_buys_eur,

                "gross_sells_eur":
                    gross_sells_eur,

                "net_trade_flow_eur":
                    (
                        gross_buys_eur
                        - gross_sells_eur
                    ),
            }
        )

    return (
        pd.DataFrame(
            daily_records
        ),
        pd.DataFrame(
            holding_records
        ),
    )