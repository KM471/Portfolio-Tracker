import math

import pandas as pd

from trading212 import get_account_summary
from history_cache import get_cached_history


def _numeric_total(series):
    return (
        pd.to_numeric(
            series,
            errors="coerce",
        )
        .fillna(0)
        .sum()
    )


def _xnpv(rate, cash_flows):
    if rate <= -1:
        return float("inf")

    first_date = cash_flows[0][0]

    total = 0.0

    for cash_date, amount in cash_flows:
        years = (
            cash_date - first_date
        ).total_seconds() / (
            365.0 * 24 * 60 * 60
        )

        try:
            total += amount / (
                (1 + rate) ** years
            )
        except (OverflowError, ZeroDivisionError):
            return float("inf")

    return total


def _xirr(cash_flows):
    cash_flows = sorted(
        cash_flows,
        key=lambda item: item[0],
    )

    amounts = [
        amount
        for _, amount in cash_flows
    ]

    if not any(amount < 0 for amount in amounts):
        return None

    if not any(amount > 0 for amount in amounts):
        return None

    candidate_rates = [
        -0.9999,
        -0.99,
        -0.90,
        -0.75,
        -0.50,
        -0.25,
        0.0,
        0.05,
        0.10,
        0.20,
        0.50,
        1.0,
        2.0,
        5.0,
        10.0,
        20.0,
        50.0,
        100.0,
    ]

    previous_rate = candidate_rates[0]
    previous_value = _xnpv(
        previous_rate,
        cash_flows,
    )

    for current_rate in candidate_rates[1:]:
        current_value = _xnpv(
            current_rate,
            cash_flows,
        )

        if not (
            math.isfinite(previous_value)
            and math.isfinite(current_value)
        ):
            previous_rate = current_rate
            previous_value = current_value
            continue

        if previous_value == 0:
            return previous_rate

        if current_value == 0:
            return current_rate

        if previous_value * current_value < 0:
            low = previous_rate
            high = current_rate

            for _ in range(200):
                middle = (low + high) / 2

                middle_value = _xnpv(
                    middle,
                    cash_flows,
                )

                if abs(middle_value) < 0.000001:
                    return middle

                low_value = _xnpv(
                    low,
                    cash_flows,
                )

                if low_value * middle_value <= 0:
                    high = middle
                else:
                    low = middle

            return (low + high) / 2

        previous_rate = current_rate
        previous_value = current_value

    return None


def _calculate_mwr(
    transactions,
    current_value,
    account_currency,
):
    if transactions.empty:
        return None

    cash_flows = transactions.copy()

    cash_flows["date"] = pd.to_datetime(
        cash_flows["dateTime"],
        utc=True,
        errors="coerce",
    )

    cash_flows["amount"] = pd.to_numeric(
        cash_flows["amount"],
        errors="coerce",
    )

    cash_flows = cash_flows.dropna(
        subset=[
            "date",
            "amount",
        ]
    )

    if cash_flows.empty:
        return None

    currencies = set(
        cash_flows["currency"].dropna()
    )

    if currencies and currencies != {
        account_currency
    }:
        return None

    dated_flows = []

    for row in cash_flows.itertuples():
        investor_cash_flow = (
            -float(row.amount)
        )

        dated_flows.append(
            (
                row.date,
                investor_cash_flow,
            )
        )

    current_date = pd.Timestamp.now(
        tz="UTC"
    )

    dated_flows.append(
        (
            current_date,
            float(current_value),
        )
    )

    return _xirr(dated_flows)


def get_performance_summary():
    # Current account value remains live.
    account = get_account_summary()

    # Historical data comes from the cache.
    transactions, orders, dividends = (
        get_cached_history()
    )

    deposits = _numeric_total(
        transactions.loc[
            transactions["type"] == "DEPOSIT",
            "amount",
        ]
    )

    withdrawals = _numeric_total(
        transactions.loc[
            transactions["type"] == "WITHDRAW",
            "amount",
        ]
    )

    net_contributions = (
        deposits + withdrawals
    )

    realised_pnl = _numeric_total(
        orders["realised_pnl"]
    )

    taxes = _numeric_total(
        orders["taxes"]
    )

    unconverted_tax_items = int(
        _numeric_total(
            orders["unconverted_tax_count"]
        )
    )

    if dividends.empty:
        dividend_income = 0.0
    else:
        dividend_income = _numeric_total(
            dividends["amountInEuro"]
        )

    current_value = float(
        account["totalValue"]
    )

    unrealised_pnl = float(
        account["investments"][
            "unrealizedProfitLoss"
        ]
    )

    total_account_gain = (
        current_value
        - net_contributions
    )

    if net_contributions > 0:
        simple_return_pct = (
            total_account_gain
            / net_contributions
        )
    else:
        simple_return_pct = 0.0

    money_weighted_return = (
        _calculate_mwr(
            transactions,
            current_value,
            account["currency"],
        )
    )

    return {
        "current_value": current_value,
        "gross_deposits": deposits,
        "gross_withdrawals": withdrawals,
        "net_contributions": net_contributions,
        "realised_pnl": realised_pnl,
        "unrealised_pnl": unrealised_pnl,
        "dividend_income": dividend_income,
        "taxes": taxes,
        "total_account_gain": total_account_gain,
        "simple_return_pct": simple_return_pct,
        "money_weighted_return": money_weighted_return,
        "unconverted_tax_items": unconverted_tax_items,
    }