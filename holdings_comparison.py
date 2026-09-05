import pandas as pd

from current_holdings_analytics import (
    get_all_current_holdings_analytics,
)


PERIODS = [
    "1M",
    "3M",
    "1Y",
]


def get_holdings_comparison(
    force_refresh=False,
):
    """
    Combine current-holdings analytics across 1M, 3M and 1Y.

    Each row represents one position currently held.
    """

    (
        portfolio_summaries,
        holdings_by_period,
    ) = get_all_current_holdings_analytics(
        force_refresh=force_refresh,
    )

    if "1M" not in holdings_by_period:
        raise ValueError(
            "1M holdings analytics are unavailable."
        )

    base = holdings_by_period[
        "1M"
    ].copy()

    if base.empty:
        return (
            portfolio_summaries,
            pd.DataFrame(),
        )

    comparison = base[
        [
            "ticker",
            "display_ticker",
            "company",
            "current_value_eur",
            "current_weight_pct",
            "unrealised_pnl",
        ]
    ].copy()

    for period in PERIODS:

        holdings = (
            holdings_by_period[
                period
            ]
            .copy()
        )

        suffix = period.lower()

        period_metrics = holdings[
            [
                "ticker",
                "return_pct",
                "beta",
                "beta_contribution",
                "annualised_volatility_pct",
                "correlation",
                "variance_contribution_pct",
            ]
        ].copy()

        period_metrics = (
            period_metrics.rename(
                columns={
                    "return_pct":
                        f"return_{suffix}_pct",

                    "beta":
                        f"beta_{suffix}",

                    "beta_contribution":
                        f"beta_contribution_{suffix}",

                    "annualised_volatility_pct":
                        f"volatility_{suffix}_pct",

                    "correlation":
                        f"correlation_{suffix}",

                    "variance_contribution_pct":
                        f"risk_contribution_{suffix}_pct",
                }
            )
        )

        comparison = (
            comparison.merge(
                period_metrics,
                on="ticker",
                how="left",
            )
        )

    comparison = (
        comparison
        .sort_values(
            "current_weight_pct",
            ascending=False,
        )
        .reset_index(
            drop=True
        )
    )

    return (
        portfolio_summaries,
        comparison,
    )


def get_holdings_risk_validation(
    force_refresh=False,
):
    """
    Validate that individual beta contributions reproduce the
    portfolio beta and variance contributions sum to ~100%.
    """

    (
        portfolio_summaries,
        comparison,
    ) = get_holdings_comparison(
        force_refresh=force_refresh,
    )

    records = []

    for period in PERIODS:

        suffix = period.lower()

        portfolio_row = (
            portfolio_summaries[
                portfolio_summaries[
                    "period"
                ] == period
            ]
        )

        if portfolio_row.empty:
            continue

        portfolio_beta = float(
            portfolio_row.iloc[0][
                "beta"
            ]
        )

        beta_contribution_sum = float(
            comparison[
                f"beta_contribution_{suffix}"
            ].sum()
        )

        risk_contribution_sum = float(
            comparison[
                f"risk_contribution_{suffix}_pct"
            ].sum()
        )

        records.append(
            {
                "period":
                    period,

                "portfolio_beta":
                    portfolio_beta,

                "beta_contribution_sum":
                    beta_contribution_sum,

                "beta_difference":
                    beta_contribution_sum
                    - portfolio_beta,

                "risk_contribution_sum_pct":
                    risk_contribution_sum,
            }
        )

    return pd.DataFrame(
        records
    )