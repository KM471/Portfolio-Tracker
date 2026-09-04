import math
import numpy as np
import pandas as pd

from performance_metrics import get_performance_metrics


def _xnpv(rate, cashflows):
    """
    Present value of irregular dated cash flows.

    cashflows must contain:
        date
        cash_flow
    """

    if rate <= -1:
        return np.nan

    start_date = cashflows.iloc[0]["date"]

    total = 0.0

    for _, row in cashflows.iterrows():

        years = (
            row["date"] - start_date
        ).days / 365.25

        total += (
            row["cash_flow"]
            /
            ((1 + rate) ** years)
        )

    return total


def _bisect_root(
    cashflows,
    low,
    high,
    tolerance=1e-10,
    max_iterations=300,
):

    low_value = _xnpv(
        low,
        cashflows,
    )

    high_value = _xnpv(
        high,
        cashflows,
    )

    if (
        not np.isfinite(low_value)
        or not np.isfinite(high_value)
        or low_value * high_value > 0
    ):
        return None

    for _ in range(
        max_iterations
    ):

        middle = (
            low + high
        ) / 2

        middle_value = _xnpv(
            middle,
            cashflows,
        )

        if not np.isfinite(
            middle_value
        ):
            return None

        if abs(
            middle_value
        ) < tolerance:
            return middle

        if (
            low_value
            * middle_value
            <= 0
        ):
            high = middle
            high_value = (
                middle_value
            )

        else:
            low = middle
            low_value = (
                middle_value
            )

    return (
        low + high
    ) / 2


def _calculate_xirr(
    dated_flows,
    terminal_value,
    terminal_date,
):
    """
    Investor-perspective XIRR.

    Deposits into the account are negative cash flows.
    Withdrawals are positive cash flows.
    Final portfolio value is a positive terminal cash flow.
    """

    flows = (
        dated_flows.copy()
    )

    flows["date"] = (
        pd.to_datetime(
            flows["date"],
            errors="coerce",
        )
        .dt.normalize()
    )

    flows["cash_flow"] = (
        pd.to_numeric(
            flows["cash_flow"],
            errors="coerce",
        )
        .fillna(0.0)
    )

    flows = flows[
        flows["cash_flow"] != 0
    ].copy()

    terminal = pd.DataFrame(
        {
            "date": [
                pd.to_datetime(
                    terminal_date
                ).normalize()
            ],
            "cash_flow": [
                float(
                    terminal_value
                )
            ],
        }
    )

    flows = pd.concat(
        [
            flows,
            terminal,
        ],
        ignore_index=True,
    )

    flows = (
        flows
        .groupby(
            "date",
            as_index=False,
        )["cash_flow"]
        .sum()
        .sort_values("date")
        .reset_index(drop=True)
    )

    if (
        not (
            (flows["cash_flow"] < 0).any()
            and
            (flows["cash_flow"] > 0).any()
        )
    ):
        return np.nan, 0

    # Scan across a wide set of possible annualised rates.
    # This is more robust than assuming one narrow bracket.
    candidate_rates = np.concatenate(
        [
            np.linspace(
                -0.9999,
                -0.5,
                250,
            ),
            np.linspace(
                -0.5,
                1.0,
                500,
            ),
            np.linspace(
                1.0,
                10.0,
                400,
            ),
            np.linspace(
                10.0,
                100.0,
                250,
            ),
        ]
    )

    roots = []

    previous_rate = (
        candidate_rates[0]
    )

    previous_value = _xnpv(
        previous_rate,
        flows,
    )

    for rate in candidate_rates[1:]:

        value = _xnpv(
            rate,
            flows,
        )

        if (
            np.isfinite(previous_value)
            and np.isfinite(value)
            and previous_value * value < 0
        ):

            root = _bisect_root(
                flows,
                previous_rate,
                rate,
            )

            if root is not None:

                if not any(
                    abs(
                        root
                        - existing
                    )
                    < 1e-6
                    for existing
                    in roots
                ):
                    roots.append(
                        root
                    )

        previous_rate = rate
        previous_value = value

    if not roots:
        return np.nan, 0

    # Normally there will be exactly one economically
    # meaningful root. If multiple exist, prefer the one
    # closest to zero and report the root count separately.
    selected = min(
        roots,
        key=lambda x: abs(x),
    )

    return (
        float(selected),
        len(roots),
    )


def get_return_metrics(
    force_refresh=False,
):

    history, performance = (
        get_performance_metrics(
            force_refresh=force_refresh,
        )
    )

    history = (
        history
        .sort_values("date")
        .reset_index(drop=True)
    )

    first_date = (
        pd.to_datetime(
            history.iloc[0]["date"]
        )
    )

    last_date = (
        pd.to_datetime(
            history.iloc[-1]["date"]
        )
    )

    elapsed_days = (
        last_date
        - first_date
    ).days

    elapsed_years = (
        elapsed_days
        / 365.25
    )

    if elapsed_years <= 0:
        raise ValueError(
            "Portfolio history is too short "
            "to annualise returns."
        )

    # TWR annualised return / CAGR.
    portfolio_growth = float(
        history.iloc[-1][
            "portfolio_growth_index"
        ]
    )

    benchmark_growth = float(
        history.iloc[-1][
            "benchmark_growth_index"
        ]
    )

    portfolio_cagr = (
        portfolio_growth
        ** (
            1 / elapsed_years
        )
        - 1
    )

    benchmark_cagr = (
        benchmark_growth
        ** (
            1 / elapsed_years
        )
        - 1
    )

    # Actual portfolio MWR / XIRR.
    # external_flow_eur is account-perspective:
    #
    # deposit  = positive
    # withdraw = negative
    #
    # XIRR needs investor-perspective signs,
    # so we invert them.
    portfolio_flows = history[
        [
            "date",
            "external_flow_eur",
        ]
    ].copy()

    portfolio_flows[
        "cash_flow"
    ] = (
        -portfolio_flows[
            "external_flow_eur"
        ]
    )

    portfolio_xirr, (
        portfolio_root_count
    ) = _calculate_xirr(
        portfolio_flows[
            [
                "date",
                "cash_flow",
            ]
        ],
        terminal_value=float(
            history.iloc[-1][
                "portfolio_value_eur"
            ]
        ),
        terminal_date=last_date,
    )

    # Synthetic S&P 500 MWR.
    #
    # benchmark_flow_eur represents money entering/leaving
    # the synthetic benchmark, so signs are inverted here too.
    benchmark_flows = history[
        [
            "date",
            "benchmark_flow_eur",
        ]
    ].copy()

    benchmark_flows[
        "cash_flow"
    ] = (
        -benchmark_flows[
            "benchmark_flow_eur"
        ]
    )

    benchmark_xirr, (
        benchmark_root_count
    ) = _calculate_xirr(
        benchmark_flows[
            [
                "date",
                "cash_flow",
            ]
        ],
        terminal_value=float(
            history.iloc[-1][
                "benchmark_value_eur"
            ]
        ),
        terminal_date=last_date,
    )

    summary = {

        "elapsed_days":
            int(elapsed_days),

        "elapsed_years":
            float(elapsed_years),

        "portfolio_twr_pct":
            float(
                performance[
                    "portfolio_twr_pct"
                ]
            ),

        "benchmark_twr_pct":
            float(
                performance[
                    "benchmark_twr_pct"
                ]
            ),

        "portfolio_cagr_pct":
            float(
                portfolio_cagr
                * 100
            ),

        "benchmark_cagr_pct":
            float(
                benchmark_cagr
                * 100
            ),

        "money_weighted_return_pct":
            (
                float(
                    portfolio_xirr
                    * 100
                )
                if np.isfinite(
                    portfolio_xirr
                )
                else np.nan
            ),

        "benchmark_mwr_pct":
            (
                float(
                    benchmark_xirr
                    * 100
                )
                if np.isfinite(
                    benchmark_xirr
                )
                else np.nan
            ),

        "portfolio_xirr_root_count":
            int(
                portfolio_root_count
            ),

        "benchmark_xirr_root_count":
            int(
                benchmark_root_count
            ),
    }

    return summary