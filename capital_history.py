import pandas as pd

from history_cache import get_cached_transactions


# ============================================================
# PREPARE TRADING 212 CASH TRANSACTIONS
# ============================================================

def _prepare_transactions():

    transactions = (
        get_cached_transactions()
        .copy()
    )

    if transactions.empty:
        return transactions

    transactions["dateTime"] = pd.to_datetime(
        transactions["dateTime"],
        utc=True,
        errors="coerce",
    )

    transactions["date"] = (
        transactions["dateTime"]
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

    transactions["currency"] = (
        transactions["currency"]
        .astype(str)
        .str.upper()
    )

    transactions = transactions.dropna(
        subset=[
            "date",
            "amount",
            "type",
        ]
    )

    # --------------------------------------------------------
    # Our Trading 212 account is EUR.
    #
    # DEPOSIT:
    # money entering the investment account
    #
    # WITHDRAW:
    # money leaving the investment account
    # including money moved out for card spending
    # --------------------------------------------------------

    non_eur = transactions[
        transactions["currency"] != "EUR"
    ]

    if not non_eur.empty:
        currencies = sorted(
            non_eur[
                "currency"
            ]
            .dropna()
            .unique()
            .tolist()
        )

        raise ValueError(
            "Non-EUR cash transactions found: "
            f"{currencies}. "
            "FX conversion needs to be added."
        )

    transactions["capital_flow_eur"] = 0.0

    deposit_mask = (
        transactions["type"]
        == "DEPOSIT"
    )

    withdrawal_mask = (
        transactions["type"]
        == "WITHDRAW"
    )

    transactions.loc[
        deposit_mask,
        "capital_flow_eur",
    ] = (
        transactions.loc[
            deposit_mask,
            "amount",
        ]
        .abs()
    )

    transactions.loc[
        withdrawal_mask,
        "capital_flow_eur",
    ] = (
        -transactions.loc[
            withdrawal_mask,
            "amount",
        ]
        .abs()
    )

    transactions = transactions[
        deposit_mask
        | withdrawal_mask
    ].copy()

    transactions = (
        transactions
        .sort_values(
            [
                "date",
                "dateTime",
            ]
        )
        .reset_index(
            drop=True
        )
    )

    return transactions


# ============================================================
# BUILD DAILY NET CAPITAL HISTORY
# ============================================================

def get_capital_history():

    transactions = (
        _prepare_transactions()
    )

    if transactions.empty:
        return pd.DataFrame()

    first_date = (
        transactions[
            "date"
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

    calendar = pd.date_range(
        start=first_date,
        end=today,
        freq="D",
    )

    daily = (
        transactions
        .groupby(
            "date"
        )
        .agg(
            deposits_eur=(
                "capital_flow_eur",
                lambda values: (
                    values[
                        values > 0
                    ]
                    .sum()
                ),
            ),

            withdrawals_eur=(
                "capital_flow_eur",
                lambda values: (
                    -values[
                        values < 0
                    ]
                    .sum()
                ),
            ),

            net_flow_eur=(
                "capital_flow_eur",
                "sum",
            ),

            transaction_count=(
                "capital_flow_eur",
                "size",
            ),
        )
        .reindex(
            calendar
        )
    )

    daily.index.name = "date"

    daily[
        [
            "deposits_eur",
            "withdrawals_eur",
            "net_flow_eur",
        ]
    ] = (
        daily[
            [
                "deposits_eur",
                "withdrawals_eur",
                "net_flow_eur",
            ]
        ]
        .fillna(0.0)
    )

    daily[
        "transaction_count"
    ] = (
        daily[
            "transaction_count"
        ]
        .fillna(0)
        .astype(int)
    )

    # --------------------------------------------------------
    # This is the line we eventually plot on the dashboard.
    #
    # Deposit increases invested capital.
    # Withdrawal decreases invested capital.
    # --------------------------------------------------------

    daily[
        "net_capital_invested_eur"
    ] = (
        daily[
            "net_flow_eur"
        ]
        .cumsum()
    )

    daily = (
        daily
        .reset_index()
    )

    return daily