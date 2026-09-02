from pathlib import Path

import pandas as pd
import yfinance as yf

from history_cache import get_cached_orders
from fx_data import get_all_fx_history


BENCHMARK_SYMBOL = "SPY"

CACHE_DIR = (
    Path.home()
    / ".portfolio_intelligence_cache"
)

CACHE_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

BENCHMARK_CACHE_FILE = (
    CACHE_DIR
    / "spy_benchmark.csv"
)


# ============================================================
# TRADING 212 ORDERS
# ============================================================

def _prepare_orders():

    orders = (
        get_cached_orders()
        .copy()
    )

    orders = orders[
        (orders["status"] == "FILLED")
        & (
            orders["side"]
            .isin(["BUY", "SELL"])
        )
    ].copy()

    orders["filled_at"] = (
        pd.to_datetime(
            orders["filled_at"],
            utc=True,
            errors="coerce",
        )
    )

    orders["trade_date"] = (
        orders["filled_at"]
        .dt.tz_convert(None)
        .dt.normalize()
    )

    orders["filled_value"] = (
        pd.to_numeric(
            orders["filled_value"],
            errors="coerce",
        )
    )

    orders["net_value"] = (
        pd.to_numeric(
            orders["net_value"],
            errors="coerce",
        )
    )

    # Older Trading 212 trades can have no filled_value.
    # net_value is therefore used as the fallback.
    orders["trade_value_eur"] = (
        orders["filled_value"]
        .fillna(
            orders["net_value"]
        )
        .abs()
    )

    orders = orders.dropna(
        subset=[
            "trade_date",
            "trade_value_eur",
            "side",
        ]
    )

    orders = orders.sort_values(
        [
            "trade_date",
            "filled_at",
        ]
    ).reset_index(
        drop=True
    )

    return orders


# ============================================================
# S&P 500 PRICE HISTORY
# ============================================================

def _download_benchmark_prices(
    start_date,
    end_date,
):

    download_end = (
        pd.Timestamp(end_date)
        + pd.Timedelta(days=1)
    )

    raw = yf.download(
        BENCHMARK_SYMBOL,
        start=pd.Timestamp(
            start_date
        ).strftime("%Y-%m-%d"),
        end=download_end.strftime(
            "%Y-%m-%d"
        ),
        auto_adjust=True,
        progress=False,
    )

    if raw.empty:
        raise ValueError(
            "Yahoo Finance returned no "
            "S&P 500 benchmark data."
        )

    close = raw["Close"]

    # yfinance can return a DataFrame here
    # depending on its current column format.
    if isinstance(
        close,
        pd.DataFrame,
    ):
        close = close.iloc[:, 0]

    history = pd.DataFrame(
        {
            "date": (
                pd.to_datetime(
                    close.index
                )
                .tz_localize(None)
                .normalize()
            ),
            "price_usd": (
                pd.to_numeric(
                    close.values,
                    errors="coerce",
                )
            ),
        }
    )

    history = history.dropna()

    history = history.drop_duplicates(
        subset=["date"],
        keep="last",
    )

    history.to_csv(
        BENCHMARK_CACHE_FILE,
        index=False,
    )

    return history


def _get_benchmark_prices(
    start_date,
    end_date,
    force_refresh=False,
):

    start_date = pd.Timestamp(
        start_date
    ).normalize()

    end_date = pd.Timestamp(
        end_date
    ).normalize()

    if (
        BENCHMARK_CACHE_FILE.exists()
        and not force_refresh
    ):

        try:

            cached = pd.read_csv(
                BENCHMARK_CACHE_FILE
            )

            cached["date"] = (
                pd.to_datetime(
                    cached["date"],
                    errors="coerce",
                )
                .dt.normalize()
            )

            cached["price_usd"] = (
                pd.to_numeric(
                    cached[
                        "price_usd"
                    ],
                    errors="coerce",
                )
            )

            cached = (
                cached
                .dropna()
                .sort_values("date")
            )

            if (
                not cached.empty
                and cached[
                    "date"
                ].min()
                <= start_date
                and cached[
                    "date"
                ].max()
                >= end_date
            ):

                return cached[
                    (
                        cached["date"]
                        >= start_date
                    )
                    & (
                        cached["date"]
                        <= end_date
                    )
                ].copy()

        except Exception:
            pass

    return _download_benchmark_prices(
        start_date,
        end_date,
    )


# ============================================================
# COUNTERFACTUAL S&P 500 PORTFOLIO
# ============================================================

def get_benchmark_history(
    force_refresh=False,
):

    orders = _prepare_orders()

    if orders.empty:
        return pd.DataFrame()

    first_date = (
        orders[
            "trade_date"
        ]
        .min()
        .normalize()
    )

    today = (
        pd.Timestamp.now(
            tz="UTC"
        )
        .tz_convert(None)
        .normalize()
    )

    prices = _get_benchmark_prices(
        first_date,
        today,
        force_refresh=force_refresh,
    )

    last_date = (
        prices["date"]
        .max()
        .normalize()
    )

    # --------------------------------------------------------
    # USD -> EUR historical FX
    # --------------------------------------------------------

    fx = get_all_fx_history(
        ["USD"],
        start_date=(
            first_date.strftime(
                "%Y-%m-%d"
            )
        ),
        force_refresh=force_refresh,
    ).copy()

    fx["date"] = (
        pd.to_datetime(
            fx["date"],
            errors="coerce",
        )
        .dt.normalize()
    )

    fx["rate_to_eur"] = (
        pd.to_numeric(
            fx["rate_to_eur"],
            errors="coerce",
        )
    )

    fx = fx[
        fx["currency"] == "USD"
    ].copy()

    # --------------------------------------------------------
    # Daily calendar
    # --------------------------------------------------------

    calendar = pd.date_range(
        first_date,
        last_date,
        freq="D",
    )

    price_series = (
        prices
        .set_index("date")[
            "price_usd"
        ]
        .reindex(calendar)
        .ffill()
        .bfill()
    )

    fx_series = (
        fx
        .set_index("date")[
            "rate_to_eur"
        ]
        .reindex(calendar)
        .ffill()
        .bfill()
    )

    # S&P 500 value expressed in EUR
    price_eur = (
        price_series
        * fx_series
    )

    orders_by_date = {
        date: group
        for date, group
        in orders.groupby(
            "trade_date"
        )
    }

    benchmark_units = 0.0

    net_invested_eur = 0.0

    records = []

    # ========================================================
    # APPLY SAME CASH FLOWS AS REAL PORTFOLIO
    # ========================================================

    for date in calendar:

        current_price_eur = float(
            price_eur.loc[date]
        )

        gross_buys_eur = 0.0
        gross_sells_eur = 0.0
        trade_count = 0

        day_orders = (
            orders_by_date.get(
                date
            )
        )

        if day_orders is not None:

            for _, order in (
                day_orders.iterrows()
            ):

                value_eur = float(
                    order[
                        "trade_value_eur"
                    ]
                )

                if (
                    order["side"]
                    == "BUY"
                ):

                    benchmark_units += (
                        value_eur
                        / current_price_eur
                    )

                    net_invested_eur += (
                        value_eur
                    )

                    gross_buys_eur += (
                        value_eur
                    )

                elif (
                    order["side"]
                    == "SELL"
                ):

                    benchmark_units -= (
                        value_eur
                        / current_price_eur
                    )

                    net_invested_eur -= (
                        value_eur
                    )

                    gross_sells_eur += (
                        value_eur
                    )

                trade_count += 1

        benchmark_value_eur = (
            benchmark_units
            * current_price_eur
        )

        benchmark_gain_eur = (
            benchmark_value_eur
            - net_invested_eur
        )

        records.append(
            {
                "date": date,

                "benchmark_price_eur": (
                    current_price_eur
                ),

                "benchmark_units": (
                    benchmark_units
                ),

                "benchmark_value_eur": (
                    benchmark_value_eur
                ),

                "net_invested_eur": (
                    net_invested_eur
                ),

                "benchmark_gain_eur": (
                    benchmark_gain_eur
                ),

                "gross_buys_eur": (
                    gross_buys_eur
                ),

                "gross_sells_eur": (
                    gross_sells_eur
                ),

                "trade_count": (
                    trade_count
                ),
            }
        )

    return pd.DataFrame(
        records
    )