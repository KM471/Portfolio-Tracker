import html
import math

import numpy as np
import pandas as pd
import streamlit as st

from trading212 import get_account_summary
from performance_metrics import get_performance_metrics
from return_metrics import get_return_metrics
from period_analytics import get_all_period_analytics
from holdings_comparison import get_holdings_comparison

from dashboard_charts import (
    render_growth_chart,
    render_allocation_donut,
    render_weighted_holdings_strip,
    render_capital_chart,
    render_profit_chart,
    render_drawdown_chart,
    render_rolling_beta,
    render_rolling_volatility,
    render_holding_returns,
    render_beta_contribution,
    render_risk_contribution,
)


# ============================================================
# Constants
# ============================================================

EURO = "\u20ac"


# ============================================================
# Page config
# ============================================================

st.set_page_config(
    page_title="Portfolio Intelligence",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="locked",
)


# ============================================================
# Styling
# ============================================================

st.html(
    """
    <style>

    @import url(
        'https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&display=swap'
    );

    :root {
        --bg: #0d1117;
        --panel: #151b25;
        --border: #243042;
        --text: #e6ebf2;
        --muted: #8593a8;
        --accent: #4c9dff;
        --positive: #3fd28b;
        --negative: #ff6b7a;
    }

    html,
    body,
    [class*="css"],
    [data-testid="stAppViewContainer"] {
        font-family: 'Manrope', sans-serif;
    }

    .stApp {
        background: var(--bg);
        color: var(--text);
    }

    header[data-testid="stHeader"] {
        background: transparent !important;
        height: 2rem !important;
        min-height: 2rem !important;
    }

    [data-testid="stToolbar"],
    [data-testid="stDecoration"],
    #MainMenu,
    footer {
        display: none !important;
    }

    .block-container {
        padding-top: 0.6rem;
        padding-bottom: 1.4rem;
        max-width: 1500px;
    }

    .block-container [data-testid="stVerticalBlock"] {
        gap: 0.72rem;
    }

    [data-testid="stSidebar"] {
        background: #10151e;
        border-right: 1px solid var(--border);
    }

    [data-testid="stSidebar"] > div {
        padding-top: 1.25rem;
    }

    .sidebar-brand {
        font-size: 18px;
        font-weight: 800;
        color: var(--text);
        letter-spacing: -0.4px;
        padding: 2px 8px 16px 8px;
    }

    [data-testid="stSidebar"]
    div[role="radiogroup"] {
        gap: 3px;
    }

    [data-testid="stSidebar"]
    div[role="radiogroup"]
    label {
        width: 100%;
        padding: 8px 11px;
        border-radius: 8px;
        border-left: 2px solid transparent;
        color: var(--muted);
    }

    [data-testid="stSidebar"]
    div[role="radiogroup"]
    label:has(input:checked) {
        background: var(--panel);
        border-left: 2px solid var(--accent);
        color: var(--text);
    }

    [data-testid="stSidebar"]
    div[role="radiogroup"]
    label > div:first-child {
        display: none;
    }

    h1 {
        font-size: 28px !important;
        font-weight: 800 !important;
        letter-spacing: -0.8px !important;
        color: var(--text) !important;
        margin-top: 0 !important;
        margin-bottom: 0 !important;
    }

    h2 {
        font-size: 19px !important;
        font-weight: 700 !important;
        color: var(--text) !important;
        margin-top: 0.4rem !important;
    }

    h3 {
        font-size: 16px !important;
        font-weight: 700 !important;
        color: var(--text) !important;
    }

    .pi-card {
        background: var(--panel);
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 14px 15px;
        min-height: 94px;
        box-sizing: border-box;
    }

    .pi-card.compact-card {
        padding: 11px 13px;
        min-height: 78px;
    }

    .pi-label {
        color: var(--muted);
        font-size: 11px;
        font-weight: 500;
        margin-bottom: 5px;
    }

    .pi-value {
        color: var(--text);
        font-size: 24px;
        line-height: 1.08;
        font-weight: 800;
        letter-spacing: -0.65px;
    }

    .compact-card .pi-value {
        font-size: 20px;
    }

    .pi-value-small {
        color: var(--text);
        font-size: 17px;
        line-height: 1.1;
        font-weight: 750;
    }

    .pi-sub {
        color: var(--muted);
        font-size: 10px;
        margin-top: 7px;
        line-height: 1.35;
    }

    .pi-positive {
        color: var(--positive) !important;
    }

    .pi-negative {
        color: var(--negative) !important;
    }

    .pi-muted {
        color: var(--muted) !important;
    }

    .hero-label {
        color: var(--muted);
        font-size: 10px;
        font-weight: 600;
        margin-bottom: 5px;
    }

    .hero-value {
        color: var(--text);
        font-size: 37px;
        font-weight: 800;
        letter-spacing: -1.25px;
        line-height: 1;
    }

    .hero-profit {
        font-size: 11px;
        margin-top: 7px;
        line-height: 1.55;
    }

    .section-label {
        font-size: 15px;
        font-weight: 750;
        color: var(--text);
        margin-bottom: 2px;
    }

    .section-note {
        color: var(--muted);
        font-size: 10px;
        line-height: 1.45;
    }

    div[data-testid="stRadio"]
    div[role="radiogroup"] {
        gap: 3px;
    }

    div[data-testid="stRadio"]
    div[role="radiogroup"]
    label {
        background: transparent;
        border: 1px solid var(--border);
        border-radius: 999px;
        padding: 3px 9px;
        min-height: 27px;
    }

    div[data-testid="stRadio"]
    div[role="radiogroup"]
    label:has(input:checked) {
        background: var(--accent);
        border-color: var(--accent);
        color: #07111f;
    }

    div[data-testid="stRadio"]
    div[role="radiogroup"]
    label > div:first-child {
        display: none;
    }

    .stButton > button {
        border: 1px solid var(--border);
        border-radius: 8px;
        background: transparent;
        color: var(--text);
        min-height: 32px;
        font-family: 'Manrope';
        font-weight: 600;
        font-size: 12px;
    }

    .stButton > button:hover {
        border-color: var(--accent);
        color: var(--accent);
    }

    [data-testid="stDataFrame"] {
        border: 1px solid var(--border);
        border-radius: 11px;
        overflow: hidden;
    }

    [data-testid="stCaptionContainer"] {
        color: var(--muted);
        font-size: 10px;
    }

    </style>
    """
)


# ============================================================
# Formatting
# ============================================================

def format_pct(value):
    if pd.isna(value):
        return "N/A"

    return f"{float(value):.2f}%"


def format_signed_pct(value):
    if pd.isna(value):
        return "N/A"

    return f"{float(value):+.2f}%"


def format_number(value):
    if pd.isna(value):
        return "N/A"

    return f"{float(value):.2f}"


def format_eur(value):
    if pd.isna(value):
        return "N/A"

    return f"{EURO}{float(value):,.2f}"


def format_signed_eur(value):
    if pd.isna(value):
        return "N/A"

    value = float(value)

    sign = "+" if value >= 0 else "-"

    return (
        f"{sign}{EURO}{abs(value):,.2f}"
    )


def format_signed_pp(value):
    if pd.isna(value):
        return "N/A"

    return f"{float(value):+.2f} pp"


def period_label(period):
    return {
        "FULL": "Full history",
        "1Y": "1 year",
        "3M": "3 months",
        "1M": "1 month",
    }.get(
        period,
        period,
    )


def timeframe_to_period(timeframe):
    return {
        "1M": "1M",
        "3M": "3M",
        "1Y": "1Y",
        "All": "FULL",
    }[
        timeframe
    ]


def get_period_row(
    table,
    period,
):
    rows = table[
        table["period"] == period
    ]

    if rows.empty:
        return None

    return rows.iloc[0]


# ============================================================
# HTML helpers
# ============================================================

def render_html(markup):
    st.html(
        str(markup).strip()
    )


def colour_class(value):
    try:
        value = float(value)

    except (
        ValueError,
        TypeError,
    ):
        return "pi-muted"

    if value > 0:
        return "pi-positive"

    if value < 0:
        return "pi-negative"

    return "pi-muted"


def card(
    label,
    value,
    subtext=None,
    value_tone=None,
    compact=False,
    value_class="pi-value",
):
    label = html.escape(
        str(label)
    )

    value = html.escape(
        str(value)
    )

    card_class = (
        "pi-card compact-card"
        if compact
        else
        "pi-card"
    )

    tone_class = (
        colour_class(value_tone)
        if value_tone is not None
        else ""
    )

    subtext_html = (
        ""
        if subtext is None
        else (
            '<div class="pi-sub">'
            f"{subtext}"
            "</div>"
        )
    )

    render_html(
        f"""
        <div class="{card_class}">
            <div class="pi-label">
                {label}
            </div>

            <div class="{value_class} {tone_class}">
                {value}
            </div>

            {subtext_html}
        </div>
        """
    )


def risk_period_for_overview(
    timeframe,
):
    if timeframe in [
        "1M",
        "3M",
        "1Y",
    ]:
        return timeframe

    return "1Y"


# ============================================================
# History / trailing-period helpers
# ============================================================

def clean_period_history(
    history,
):
    data = history.copy()

    data["date"] = pd.to_datetime(
        data["date"],
        errors="coerce",
    )

    numeric_columns = [
        "portfolio_value_eur",
        "benchmark_value_eur",
        "external_flow_eur",
        "portfolio_daily_return",
        "benchmark_daily_return",
        "portfolio_growth_index",
        "benchmark_growth_index",
    ]

    for column in numeric_columns:

        if column in data.columns:

            data[column] = pd.to_numeric(
                data[column],
                errors="coerce",
            )

    data = (
        data
        .dropna(
            subset=[
                "date",
            ]
        )
        .sort_values(
            "date"
        )
        .drop_duplicates(
            subset=[
                "date",
            ],
            keep="last",
        )
        .reset_index(
            drop=True
        )
    )

    return data


def calendar_target(
    last_date,
    period,
):
    last_date = pd.Timestamp(
        last_date
    )

    if period == "1M":

        return (
            last_date
            - pd.DateOffset(
                months=1
            )
        )

    if period == "3M":

        return (
            last_date
            - pd.DateOffset(
                months=3
            )
        )

    if period == "1Y":

        return (
            last_date
            - pd.DateOffset(
                years=1
            )
        )

    return None


def find_baseline_row(
    history,
    period,
):
    data = clean_period_history(
        history
    )

    valid = data.dropna(
        subset=[
            "portfolio_value_eur",
        ]
    )

    valid = valid[
        valid[
            "portfolio_value_eur"
        ] > 0
    ]

    if valid.empty:
        return None

    end_date = valid.iloc[-1][
        "date"
    ]

    if period == "FULL":

        return valid.iloc[0]

    target = calendar_target(
        end_date,
        period,
    )

    candidates = valid[
        valid[
            "date"
        ] <= target
    ]

    if candidates.empty:

        return valid.iloc[0]

    return candidates.iloc[-1]


def growth_index_return(
    start_row,
    end_row,
    index_column,
):
    if (
        index_column
        not in start_row.index
        or
        index_column
        not in end_row.index
    ):
        return math.nan

    start_value = start_row[
        index_column
    ]

    end_value = end_row[
        index_column
    ]

    if (
        pd.isna(start_value)
        or
        pd.isna(end_value)
    ):
        return math.nan

    start_value = float(
        start_value
    )

    end_value = float(
        end_value
    )

    if abs(
        start_value
    ) < 1e-12:
        return math.nan

    return (
        (
            end_value
            /
            start_value
        )
        - 1
    ) * 100


def compounded_return(
    data,
    column,
):
    if column not in data.columns:
        return math.nan

    returns = pd.to_numeric(
        data[column],
        errors="coerce",
    ).dropna()

    if returns.empty:
        return math.nan

    return (
        (
            (
                1.0
                + returns
            ).prod()
        )
        - 1.0
    ) * 100


def corrected_period_metrics(
    history,
    period,
    original_row,
):
    """
    Correct the PERFORMANCE side of a period row.

    Important:
    - 1M means one calendar month back.
    - 3M means three calendar months back.
    - 1Y means one calendar year back.
    - The baseline portfolio value, TWR, MWR and P/L all use
      the same boundary.

    Risk statistics remain from the established backend.
    """

    if (
        period == "FULL"
        or original_row is None
    ):
        return original_row.copy()

    data = clean_period_history(
        history
    )

    baseline = find_baseline_row(
        data,
        period,
    )

    if baseline is None:
        return original_row.copy()

    baseline_date = pd.Timestamp(
        baseline[
            "date"
        ]
    )

    valid_values = (
        data
        .dropna(
            subset=[
                "portfolio_value_eur",
            ]
        )
        .sort_values(
            "date"
        )
    )

    if valid_values.empty:
        return original_row.copy()

    end_row = valid_values.iloc[-1]

    end_date = pd.Timestamp(
        end_row[
            "date"
        ]
    )

    period_rows = data[
        (
            data[
                "date"
            ] > baseline_date
        )
        &
        (
            data[
                "date"
            ] <= end_date
        )
    ].copy()

    if period_rows.empty:
        return original_row.copy()

    output = original_row.copy()

    start_value = float(
        baseline[
            "portfolio_value_eur"
        ]
    )

    end_value = float(
        end_row[
            "portfolio_value_eur"
        ]
    )

    if (
        "external_flow_eur"
        in period_rows.columns
    ):

        external_flows = float(
            pd.to_numeric(
                period_rows[
                    "external_flow_eur"
                ],
                errors="coerce",
            )
            .fillna(0.0)
            .sum()
        )

    else:

        external_flows = 0.0

    portfolio_profit = (
        end_value
        - start_value
        - external_flows
    )

    portfolio_twr = growth_index_return(
        baseline,
        end_row,
        "portfolio_growth_index",
    )

    if pd.isna(
        portfolio_twr
    ):

        portfolio_twr = compounded_return(
            period_rows,
            "portfolio_daily_return",
        )

    benchmark_twr = growth_index_return(
        baseline,
        end_row,
        "benchmark_growth_index",
    )

    if pd.isna(
        benchmark_twr
    ):

        benchmark_twr = compounded_return(
            period_rows,
            "benchmark_daily_return",
        )

    relative_pp = (
        portfolio_twr
        - benchmark_twr
    )

    if (
        benchmark_twr
        > -100
    ):

        relative_pct = (
            (
                (
                    1
                    + portfolio_twr
                    / 100
                )
                /
                (
                    1
                    + benchmark_twr
                    / 100
                )
            )
            - 1
        ) * 100

    else:

        relative_pct = math.nan

    calendar_days = max(
        (
            end_date
            - baseline_date
        ).days,
        1,
    )

    portfolio_daily = pd.to_numeric(
        period_rows[
            "portfolio_daily_return"
        ],
        errors="coerce",
    ).dropna()

    if calendar_days >= 360:

        if (
            portfolio_twr
            > -100
        ):

            portfolio_cagr = (
                (
                    1
                    + portfolio_twr
                    / 100
                )
                ** (
                    365.25
                    /
                    calendar_days
                )
                - 1
            ) * 100

        else:

            portfolio_cagr = math.nan

        if (
            benchmark_twr
            > -100
        ):

            benchmark_cagr = (
                (
                    1
                    + benchmark_twr
                    / 100
                )
                ** (
                    365.25
                    /
                    calendar_days
                )
                - 1
            ) * 100

        else:

            benchmark_cagr = math.nan

    else:

        portfolio_cagr = math.nan
        benchmark_cagr = math.nan

    if portfolio_daily.empty:

        best_day = math.nan
        worst_day = math.nan
        observations = 0

    else:

        best_day = float(
            portfolio_daily.max()
            * 100
        )

        worst_day = float(
            portfolio_daily.min()
            * 100
        )

        observations = int(
            portfolio_daily.count()
        )

    output[
        "first_date"
    ] = baseline_date

    output[
        "last_date"
    ] = end_date

    output[
        "calendar_days"
    ] = calendar_days

    output[
        "trading_observations"
    ] = observations

    output[
        "starting_portfolio_value_eur"
    ] = start_value

    output[
        "ending_portfolio_value_eur"
    ] = end_value

    output[
        "portfolio_profit_eur"
    ] = portfolio_profit

    output[
        "external_flows_eur"
    ] = external_flows

    output[
        "portfolio_twr_pct"
    ] = portfolio_twr

    output[
        "benchmark_twr_pct"
    ] = benchmark_twr

    output[
        "relative_return_pp"
    ] = relative_pp

    output[
        "relative_return_pct"
    ] = relative_pct

    output[
        "portfolio_cagr_pct"
    ] = portfolio_cagr

    output[
        "benchmark_cagr_pct"
    ] = benchmark_cagr

    output[
        "best_day_pct"
    ] = best_day

    output[
        "worst_day_pct"
    ] = worst_day

    return output


def build_corrected_period_table(
    history,
    raw_period_table,
):
    rows = []

    for period in [
        "FULL",
        "1Y",
        "3M",
        "1M",
    ]:

        original = get_period_row(
            raw_period_table,
            period,
        )

        if original is None:
            continue

        corrected = corrected_period_metrics(
            history,
            period,
            original,
        )

        rows.append(
            corrected
        )

    if not rows:
        return raw_period_table.copy()

    output = pd.DataFrame(
        rows
    )

    return output.reset_index(
        drop=True
    )


def chart_first_return_date(
    history,
    baseline_date,
):
    data = clean_period_history(
        history
    )

    baseline_date = pd.Timestamp(
        baseline_date
    )

    later_dates = data.loc[
        data[
            "date"
        ] > baseline_date,
        "date",
    ]

    if later_dates.empty:
        return baseline_date

    return later_dates.iloc[0]


# ============================================================
# Money-weighted return
# ============================================================

def _xnpv(
    rate,
    cash_flows,
):
    if rate <= -1:
        return float("inf")

    base_date = cash_flows[0][0]

    total = 0.0

    for date, amount in cash_flows:

        years = (
            (
                date
                - base_date
            ).days
            /
            365.0
        )

        try:

            denominator = (
                1.0
                + rate
            ) ** years

            total += (
                amount
                /
                denominator
            )

        except (
            OverflowError,
            ZeroDivisionError,
        ):

            return float("inf")

    return total


def _solve_xirr(
    cash_flows,
):
    if len(
        cash_flows
    ) < 2:
        return math.nan

    amounts = [
        amount
        for _, amount
        in cash_flows
    ]

    if not (
        any(
            amount < 0
            for amount
            in amounts
        )
        and
        any(
            amount > 0
            for amount
            in amounts
        )
    ):
        return math.nan

    low = -0.9999

    low_value = _xnpv(
        low,
        cash_flows,
    )

    if not math.isfinite(
        low_value
    ):

        low = -0.99

        low_value = _xnpv(
            low,
            cash_flows,
        )

    candidates = [
        1.0,
        2.0,
        5.0,
        10.0,
        25.0,
        50.0,
        100.0,
        500.0,
        1000.0,
        10000.0,
    ]

    high = None

    for candidate in candidates:

        candidate_value = _xnpv(
            candidate,
            cash_flows,
        )

        if not math.isfinite(
            candidate_value
        ):
            continue

        if low_value == 0:
            return low

        if candidate_value == 0:
            return candidate

        if (
            low_value
            * candidate_value
            < 0
        ):

            high = candidate
            break

    if high is None:
        return math.nan

    for _ in range(
        200
    ):

        midpoint = (
            low
            + high
        ) / 2

        midpoint_value = _xnpv(
            midpoint,
            cash_flows,
        )

        if not math.isfinite(
            midpoint_value
        ):

            low = midpoint
            continue

        if abs(
            midpoint_value
        ) < 1e-8:

            return midpoint

        if (
            low_value
            * midpoint_value
            <= 0
        ):

            high = midpoint

        else:

            low = midpoint
            low_value = midpoint_value

        if abs(
            high
            - low
        ) < 1e-10:
            break

    return (
        low
        + high
    ) / 2


def modified_dietz_return(
    start_value,
    end_value,
    start_date,
    end_date,
    flows,
):
    total_days = max(
        (
            end_date
            - start_date
        ).days,
        1,
    )

    total_flow = 0.0
    weighted_flow = 0.0

    for date, flow in flows:

        flow = float(
            flow
        )

        total_flow += flow

        weight = (
            (
                end_date
                - date
            ).days
            /
            total_days
        )

        weighted_flow += (
            flow
            * weight
        )

    denominator = (
        start_value
        + weighted_flow
    )

    if abs(
        denominator
    ) < 1e-12:
        return math.nan

    numerator = (
        end_value
        - start_value
        - total_flow
    )

    return (
        numerator
        /
        denominator
        *
        100
    )


def calculate_period_mwr(
    history,
    first_date,
    last_date,
):
    """
    Money-weighted return using the exact same start and end
    boundary as the displayed period.

    If there are no external flows, MWR is simply the account's
    holding-period return and therefore should be very close to TWR.
    """

    data = clean_period_history(
        history
    )

    first_date = pd.Timestamp(
        first_date
    )

    last_date = pd.Timestamp(
        last_date
    )

    baseline_candidates = data[
        (
            data[
                "date"
            ] <= first_date
        )
        &
        (
            data[
                "portfolio_value_eur"
            ].notna()
        )
    ]

    if baseline_candidates.empty:
        return math.nan

    baseline = (
        baseline_candidates.iloc[-1]
    )

    start_date = pd.Timestamp(
        baseline[
            "date"
        ]
    )

    start_value = float(
        baseline[
            "portfolio_value_eur"
        ]
    )

    ending_candidates = data[
        (
            data[
                "date"
            ] <= last_date
        )
        &
        (
            data[
                "portfolio_value_eur"
            ].notna()
        )
    ]

    if ending_candidates.empty:
        return math.nan

    ending = ending_candidates.iloc[-1]

    end_date = pd.Timestamp(
        ending[
            "date"
        ]
    )

    end_value = float(
        ending[
            "portfolio_value_eur"
        ]
    )

    if (
        start_value <= 0
        or end_value < 0
    ):
        return math.nan

    period_rows = data[
        (
            data[
                "date"
            ] > start_date
        )
        &
        (
            data[
                "date"
            ] <= end_date
        )
    ].copy()

    if (
        "external_flow_eur"
        in period_rows.columns
    ):

        period_rows[
            "external_flow_eur"
        ] = pd.to_numeric(
            period_rows[
                "external_flow_eur"
            ],
            errors="coerce",
        ).fillna(
            0.0
        )

    else:

        period_rows[
            "external_flow_eur"
        ] = 0.0

    absolute_external_flow = float(
        period_rows[
            "external_flow_eur"
        ].abs().sum()
    )

    # --------------------------------------------------------
    # No money entered or left the account.
    #
    # In this case money weighting has nothing to weight.
    # The correct result is the actual start-to-end account return.
    # --------------------------------------------------------

    if absolute_external_flow < 0.005:

        return (
            (
                end_value
                /
                start_value
            )
            - 1
        ) * 100

    # --------------------------------------------------------
    # External flows occurred: use XIRR.
    # --------------------------------------------------------

    cash_flows = [
        (
            start_date,
            -start_value,
        )
    ]

    dietz_flows = []

    for row in period_rows.itertuples():

        flow = float(
            row.external_flow_eur
        )

        if abs(
            flow
        ) < 1e-9:
            continue

        # Investor perspective:
        # Deposit into account = negative cash flow.
        # Withdrawal from account = positive cash flow.
        cash_flows.append(
            (
                row.date,
                -flow,
            )
        )

        dietz_flows.append(
            (
                row.date,
                flow,
            )
        )

    cash_flows.append(
        (
            end_date,
            end_value,
        )
    )

    annual_xirr = _solve_xirr(
        cash_flows
    )

    if (
        not pd.isna(
            annual_xirr
        )
        and annual_xirr > -1
    ):

        elapsed_days = max(
            (
                end_date
                - start_date
            ).days,
            1,
        )

        try:

            period_return = (
                (
                    1
                    + annual_xirr
                )
                ** (
                    elapsed_days
                    / 365.0
                )
                - 1
            ) * 100

            if math.isfinite(
                period_return
            ):

                return period_return

        except (
            OverflowError,
            ValueError,
        ):
            pass

    return modified_dietz_return(
        start_value,
        end_value,
        start_date,
        end_date,
        dietz_flows,
    )


def full_period_mwr_from_xirr(
    annual_xirr_pct,
    first_date,
    last_date,
):
    if pd.isna(
        annual_xirr_pct
    ):
        return math.nan

    annual_rate = (
        float(
            annual_xirr_pct
        )
        /
        100.0
    )

    if annual_rate <= -1:
        return math.nan

    start = pd.Timestamp(
        first_date
    )

    end = pd.Timestamp(
        last_date
    )

    days = max(
        (
            end
            - start
        ).days,
        1,
    )

    return (
        (
            (
                1
                + annual_rate
            )
            ** (
                days
                /
                365.0
            )
        )
        - 1
    ) * 100


def build_period_mwr_map(
    history,
    period_table,
    returns,
):
    output = {}

    for period in [
        "1M",
        "3M",
        "1Y",
    ]:

        row = get_period_row(
            period_table,
            period,
        )

        if row is None:

            output[
                period
            ] = math.nan

            continue

        output[
            period
        ] = calculate_period_mwr(
            history,
            row[
                "first_date"
            ],
            row[
                "last_date"
            ],
        )

    full_row = get_period_row(
        period_table,
        "FULL",
    )

    if full_row is None:

        output[
            "FULL"
        ] = math.nan

    else:

        output[
            "FULL"
        ] = full_period_mwr_from_xirr(
            returns[
                "money_weighted_return_pct"
            ],
            full_row[
                "first_date"
            ],
            full_row[
                "last_date"
            ],
        )

    return output


# ============================================================
# Load data
# ============================================================

@st.cache_data(
    ttl=600,
    show_spinner=False,
)
def load_dashboard_data():

    history, performance = (
        get_performance_metrics()
    )

    returns = (
        get_return_metrics()
    )

    live = (
        get_account_summary()
    )

    raw_period_table = (
        get_all_period_analytics()
    )

    period_table = (
        build_corrected_period_table(
            history,
            raw_period_table,
        )
    )

    (
        current_holdings_table,
        holdings_table,
    ) = get_holdings_comparison()

    period_mwr_map = (
        build_period_mwr_map(
            history,
            period_table,
            returns,
        )
    )

    return (
        history,
        performance,
        returns,
        live,
        period_table,
        raw_period_table,
        current_holdings_table,
        holdings_table,
        period_mwr_map,
    )


if (
    "dashboard_data"
    not in st.session_state
):

    try:

        with st.spinner(
            "Loading portfolio data..."
        ):

            st.session_state[
                "dashboard_data"
            ] = load_dashboard_data()

    except Exception as error:

        st.error(
            "Unable to load portfolio data: "
            f"{error}"
        )

        st.stop()


(
    history,
    performance,
    returns,
    live,
    period_table,
    raw_period_table,
    current_holdings_table,
    holdings_table,
    period_mwr_map,
) = st.session_state[
    "dashboard_data"
]


# ============================================================
# Live account values
# ============================================================

live_total = float(
    live.get(
        "totalValue",
        performance[
            "portfolio_value_eur"
        ],
    )
)


investment_data = live.get(
    "investments",
    {},
)


unrealised_pnl = float(
    investment_data.get(
        "unrealizedProfitLoss",
        0.0,
    )
)


cash_data = live.get(
    "cash",
    {},
)


visible_cash = (
    float(
        cash_data.get(
            "availableToTrade",
            0.0,
        )
    )
    +
    float(
        cash_data.get(
            "reservedForOrders",
            0.0,
        )
    )
    +
    float(
        cash_data.get(
            "inPies",
            0.0,
        )
    )
)


# ============================================================
# Overview state
# ============================================================

def reset_overview_to_zoom():

    st.session_state[
        "overview_interaction"
    ] = "Zoom"


# ============================================================
# OVERVIEW
# ============================================================

@st.fragment
def render_overview():

    title_col, control_col = (
        st.columns(
            [
                3.5,
                2.5,
            ],
            vertical_alignment="center",
        )
    )

    with title_col:

        st.title(
            "Overview"
        )

        st.caption(
            "Performance, allocation and risk at a glance."
        )

    with control_col:

        timeframe_col, refresh_col = (
            st.columns(
                [
                    3.2,
                    1,
                ],
                vertical_alignment="center",
            )
        )

        with timeframe_col:

            timeframe = st.radio(
                "Timeframe",
                [
                    "1M",
                    "3M",
                    "1Y",
                    "All",
                ],
                index=3,
                horizontal=True,
                label_visibility="collapsed",
                key="overview_timeframe",
                on_change=(
                    reset_overview_to_zoom
                ),
            )

        with refresh_col:

            if st.button(
                "Refresh",
                use_container_width=True,
            ):

                load_dashboard_data.clear()

                st.session_state.pop(
                    "dashboard_data",
                    None,
                )

                st.rerun()

    period = timeframe_to_period(
        timeframe
    )

    selected = get_period_row(
        period_table,
        period,
    )

    risk_selected = get_period_row(
        raw_period_table,
        period,
    )

    if selected is None:

        st.error(
            "No data available for this timeframe."
        )

        return

    if risk_selected is None:
        risk_selected = selected

    # --------------------------------------------------------
    # Hero + performance
    # --------------------------------------------------------

    top_columns = st.columns(
        [
            1.35,
            1,
            1,
            1,
            1,
            1,
        ],
        vertical_alignment="center",
    )

    total_profit = float(
        performance[
            "simple_gain_eur"
        ]
    )

    with top_columns[0]:

        render_html(
            f"""
            <div style="padding:7px 0;">

                <div class="hero-label">
                    ACCOUNT VALUE
                </div>

                <div class="hero-value">
                    {format_eur(live_total)}
                </div>

                <div class="hero-profit">

                    <span class="{colour_class(total_profit)}">
                        {format_signed_eur(total_profit)}
                    </span>
                    total profit

                    <br>

                    <span class="pi-muted">
                        Net invested
                        {format_eur(
                            performance[
                                'net_capital_invested_eur'
                            ]
                        )}
                        · Cash
                        {format_eur(
                            visible_cash
                        )}
                    </span>

                    <br>

                    <span class="{colour_class(unrealised_pnl)}">
                        Unrealised
                        {format_signed_eur(
                            unrealised_pnl
                        )}
                    </span>

                </div>

            </div>
            """
        )

    portfolio_twr = float(
        selected[
            "portfolio_twr_pct"
        ]
    )

    period_mwr = (
        period_mwr_map.get(
            period,
            math.nan,
        )
    )

    benchmark_twr = float(
        selected[
            "benchmark_twr_pct"
        ]
    )

    relative = float(
        selected[
            "relative_return_pp"
        ]
    )

    period_profit = float(
        selected[
            "portfolio_profit_eur"
        ]
    )

    external_flow = float(
        selected[
            "external_flows_eur"
        ]
    )

    first_date = pd.Timestamp(
        selected[
            "first_date"
        ]
    )

    last_date = pd.Timestamp(
        selected[
            "last_date"
        ]
    )

    with top_columns[1]:

        card(
            "Portfolio TWR",
            format_signed_pct(
                portfolio_twr
            ),
            "Cash flows neutralised",
            value_tone=(
                portfolio_twr
            ),
        )

    with top_columns[2]:

        if period == "FULL":

            mwr_subtext = (
                "Cumulative money-weighted return"
            )

        elif abs(
            external_flow
        ) < 0.005:

            mwr_subtext = (
                "No external flows in period"
            )

        else:

            mwr_subtext = (
                "Cash-flow timing adjusted"
            )

        card(
            "Money-weighted return",
            format_signed_pct(
                period_mwr
            ),
            mwr_subtext,
            value_tone=(
                None
                if pd.isna(
                    period_mwr
                )
                else period_mwr
            ),
        )

    with top_columns[3]:

        card(
            "S&P 500 return",
            format_signed_pct(
                benchmark_twr
            ),
            "Mirrored cash flows",
            value_tone=(
                benchmark_twr
            ),
        )

    with top_columns[4]:

        card(
            "Performance gap",
            format_signed_pp(
                relative
            ),
            "Portfolio TWR vs S&P",
            value_tone=(
                relative
            ),
        )

    with top_columns[5]:

        if period == "FULL":

            date_text = (
                "Full history"
            )

        else:

            date_text = (
                f"{first_date.strftime('%d %b')}"
                " → "
                f"{last_date.strftime('%d %b')}"
            )

        card(
            "Period P/L",
            format_signed_eur(
                period_profit
            ),
            date_text,
            value_tone=(
                period_profit
            ),
        )

    # --------------------------------------------------------
    # Quick risk
    # --------------------------------------------------------

    render_html(
        """
        <div class="section-label">
            Quick risk
        </div>
        """
    )

    risk1, risk2, risk3, risk4 = (
        st.columns(4)
    )

    beta = float(
        risk_selected[
            "beta"
        ]
    )

    with risk1:

        beta_width = min(
            max(
                beta
                / 3
                * 100,
                0,
            ),
            100,
        )

        render_html(
            f"""
            <div class="pi-card compact-card">

                <div class="pi-label">
                    Beta
                </div>

                <div class="pi-value">
                    {beta:.2f}
                </div>

                <div style="
                    position:relative;
                    height:4px;
                    background:#243042;
                    border-radius:999px;
                    margin-top:9px;
                ">

                    <div style="
                        width:{beta_width:.1f}%;
                        height:4px;
                        background:#4c9dff;
                        border-radius:999px;
                    ">
                    </div>

                    <div style="
                        position:absolute;
                        left:33.33%;
                        top:-3px;
                        width:1px;
                        height:10px;
                        background:#8593a8;
                    ">
                    </div>

                </div>

                <div class="pi-sub">
                    Market = 1.00
                </div>

            </div>
            """
        )

    with risk2:

        card(
            "Volatility",
            format_pct(
                risk_selected[
                    "annualised_volatility_pct"
                ]
            ),
            (
                "S&amp;P "
                f"{format_pct(
                    risk_selected[
                        'benchmark_volatility_pct'
                    ]
                )}"
            ),
            compact=True,
        )

    with risk3:

        drawdown = float(
            risk_selected[
                "max_drawdown_pct"
            ]
        )

        card(
            "Max drawdown",
            format_pct(
                drawdown
            ),
            (
                f"{int(
                    risk_selected[
                        'max_drawdown_duration_days'
                    ]
                )} days · "
                "S&amp;P "
                f"{format_pct(
                    risk_selected[
                        'benchmark_max_drawdown_pct'
                    ]
                )}"
            ),
            value_tone=drawdown,
            compact=True,
        )

    with risk4:

        card(
            "Sharpe / Sortino",
            (
                f"{risk_selected['sharpe_ratio']:.2f}"
                " / "
                f"{risk_selected['sortino_ratio']:.2f}"
            ),
            "Risk-adjusted return",
            compact=True,
        )

    # --------------------------------------------------------
    # Main chart + allocation
    # --------------------------------------------------------

    chart_col, allocation_col = (
        st.columns(
            [
                2.08,
                1,
            ],
            vertical_alignment="top",
        )
    )

    with chart_col:

        render_html(
            """
            <div class="section-label">
                Portfolio vs S&amp;P 500
            </div>
            """
        )

        controls = st.columns(
            [
                1,
                1.5,
                4,
            ],
            vertical_alignment="center",
        )

        with controls[0]:

            view = st.radio(
                "View",
                [
                    "%",
                    EURO,
                ],
                horizontal=True,
                label_visibility="collapsed",
                key="overview_chart_view",
            )

        with controls[1]:

            interaction_mode = st.radio(
                "Interaction",
                [
                    "Zoom",
                    "Measure",
                ],
                horizontal=True,
                label_visibility="collapsed",
                key="overview_interaction",
            )

        chart_key = (
            f"overview_growth_"
            f"{timeframe}_"
            f"{interaction_mode}_"
            f"{view}"
        )

        chart_start = (
            chart_first_return_date(
                history,
                selected[
                    "first_date"
                ],
            )
        )

        selected_stats = render_growth_chart(
            history,
            first_date=chart_start,
            view=view,
            height=270,
            interaction_mode=(
                interaction_mode
            ),
            chart_key=chart_key,
        )

        if (
            interaction_mode
            == "Measure"
        ):

            if selected_stats is None:

                st.caption(
                    "Drag across the chart to measure "
                    "portfolio and S&P performance over "
                    "an exact period."
                )

            else:

                result_columns = st.columns(
                    [
                        1.4,
                        1,
                        1,
                        1,
                    ]
                )

                start_text = (
                    selected_stats[
                        "start_date"
                    ]
                    .strftime(
                        "%d %b %Y"
                    )
                )

                end_text = (
                    selected_stats[
                        "end_date"
                    ]
                    .strftime(
                        "%d %b %Y"
                    )
                )

                with result_columns[0]:

                    card(
                        "Selected period",
                        (
                            f"{start_text}"
                            " → "
                            f"{end_text}"
                        ),
                        compact=True,
                        value_class=(
                            "pi-value-small"
                        ),
                    )

                with result_columns[1]:

                    value = (
                        selected_stats[
                            "portfolio_return_pct"
                        ]
                    )

                    card(
                        "Portfolio",
                        format_signed_pct(
                            value
                        ),
                        value_tone=value,
                        compact=True,
                    )

                with result_columns[2]:

                    value = (
                        selected_stats[
                            "benchmark_return_pct"
                        ]
                    )

                    card(
                        "S&P 500",
                        format_signed_pct(
                            value
                        ),
                        value_tone=value,
                        compact=True,
                    )

                with result_columns[3]:

                    value = (
                        selected_stats[
                            "gap_pp"
                        ]
                    )

                    card(
                        "Gap",
                        format_signed_pp(
                            value
                        ),
                        value_tone=value,
                        compact=True,
                    )

        else:

            st.caption(
                "Drag or scroll to zoom. "
                "Changing timeframe automatically "
                "returns the chart to Zoom mode."
            )

    with allocation_col:

        render_html(
            """
            <div class="section-label">
                Allocation
            </div>

            <div class="pi-sub">
                Current portfolio weights
            </div>
            """
        )

        render_allocation_donut(
            holdings_table,
            height=245,
        )

    # --------------------------------------------------------
    # Weighted holdings
    # --------------------------------------------------------

    render_weighted_holdings_strip(
        holdings_table,
        timeframe=timeframe,
        height=118,
    )

    risk_period = (
        risk_period_for_overview(
            timeframe
        )
    )

    risk_column = (
        f"risk_contribution_"
        f"{risk_period.lower()}_pct"
    )

    risk_data = (
        holdings_table[
            [
                "display_ticker",
                "current_weight_pct",
                risk_column,
            ]
        ]
        .dropna()
        .sort_values(
            risk_column,
            ascending=False,
        )
    )

    if not risk_data.empty:

        top_risk = (
            risk_data.iloc[0]
        )

        period_note = (
            ""
            if timeframe != "All"
            else
            " Risk contribution uses the longest available 1Y window."
        )

        render_html(
            f"""
            <div style="
                color:#8593a8;
                font-size:10px;
            ">

                <span style="
                    color:#e6ebf2;
                    font-weight:650;
                ">
                    {top_risk['display_ticker']}
                </span>

                is
                {top_risk['current_weight_pct']:.1f}%
                of portfolio value and
                {top_risk[risk_column]:.1f}%
                of portfolio risk.
                {period_note}

            </div>
            """
        )


# ============================================================
# PERFORMANCE
# ============================================================

@st.fragment
def render_performance():

    st.title(
        "Performance"
    )

    st.caption(
        "Detailed return, cash-flow and benchmark analysis."
    )

    # --------------------------------------------------------
    # Recent performance
    # --------------------------------------------------------

    st.subheader(
        "Recent performance"
    )

    recent_columns = (
        st.columns(4)
    )

    for column, period in zip(
        recent_columns[:3],
        [
            "1M",
            "3M",
            "1Y",
        ],
    ):

        recent = get_period_row(
            period_table,
            period,
        )

        if recent is None:
            continue

        value = float(
            recent[
                "portfolio_twr_pct"
            ]
        )

        relative = float(
            recent[
                "relative_return_pp"
            ]
        )

        with column:

            card(
                period_label(
                    period
                ),
                format_signed_pct(
                    value
                ),
                (
                    f'<span class="{colour_class(relative)}">'
                    f"{format_signed_pp(relative)} vs S&amp;P"
                    "</span>"
                ),
                value_tone=value,
            )

    full = get_period_row(
        period_table,
        "FULL",
    )

    with recent_columns[3]:

        value = float(
            full[
                "portfolio_cagr_pct"
            ]
        )

        card(
            "Full-history CAGR",
            format_signed_pct(
                value
            ),
            (
                "S&amp;P "
                f"{format_signed_pct(
                    full[
                        'benchmark_cagr_pct'
                    ]
                )}"
            ),
            value_tone=value,
        )

    # --------------------------------------------------------
    # Selected period
    # --------------------------------------------------------

    st.subheader(
        "Period analysis"
    )

    period = st.radio(
        "Period",
        [
            "FULL",
            "1Y",
            "3M",
            "1M",
        ],
        horizontal=True,
        format_func=period_label,
        key="performance_period",
    )

    selected = get_period_row(
        period_table,
        period,
    )

    risk_selected = get_period_row(
        raw_period_table,
        period,
    )

    if selected is None:
        return

    if risk_selected is None:
        risk_selected = selected

    selected_mwr = (
        period_mwr_map.get(
            period,
            math.nan,
        )
    )

    first_date = pd.Timestamp(
        selected[
            "first_date"
        ]
    )

    last_date = pd.Timestamp(
        selected[
            "last_date"
        ]
    )

    external_flow = float(
        selected[
            "external_flows_eur"
        ]
    )

    st.caption(
        f"{first_date.strftime('%d %b %Y')}"
        " → "
        f"{last_date.strftime('%d %b %Y')}"
        " · External cash flow "
        f"{format_signed_eur(external_flow)}"
    )

    # --------------------------------------------------------
    # Return metrics
    # --------------------------------------------------------

    return_cards = (
        st.columns(4)
    )

    portfolio_twr = float(
        selected[
            "portfolio_twr_pct"
        ]
    )

    benchmark_twr = float(
        selected[
            "benchmark_twr_pct"
        ]
    )

    relative = float(
        selected[
            "relative_return_pp"
        ]
    )

    with return_cards[0]:

        card(
            "Portfolio TWR",
            format_signed_pct(
                portfolio_twr
            ),
            "Cash flows neutralised",
            value_tone=portfolio_twr,
        )

    with return_cards[1]:

        if (
            period != "FULL"
            and
            abs(
                external_flow
            ) < 0.005
        ):

            mwr_note = (
                "No external flows in period"
            )

        elif period == "FULL":

            mwr_note = (
                "Cumulative money-weighted result"
            )

        else:

            mwr_note = (
                "Cash-flow timing included"
            )

        card(
            "Money-weighted return",
            format_signed_pct(
                selected_mwr
            ),
            mwr_note,
            value_tone=(
                None
                if pd.isna(
                    selected_mwr
                )
                else selected_mwr
            ),
        )

    with return_cards[2]:

        card(
            "S&P 500 TWR",
            format_signed_pct(
                benchmark_twr
            ),
            value_tone=benchmark_twr,
        )

    with return_cards[3]:

        card(
            "Outperformance",
            format_signed_pp(
                relative
            ),
            "Portfolio TWR vs S&P",
            value_tone=relative,
        )

    # --------------------------------------------------------
    # Account / flow context
    # --------------------------------------------------------

    context_cards = (
        st.columns(4)
    )

    with context_cards[0]:

        card(
            "Starting value",
            format_eur(
                selected[
                    "starting_portfolio_value_eur"
                ]
            ),
        )

    with context_cards[1]:

        card(
            "Ending value",
            format_eur(
                selected[
                    "ending_portfolio_value_eur"
                ]
            ),
        )

    with context_cards[2]:

        period_profit = float(
            selected[
                "portfolio_profit_eur"
            ]
        )

        card(
            "Period P/L",
            format_signed_eur(
                period_profit
            ),
            value_tone=period_profit,
        )

    with context_cards[3]:

        card(
            "External cash flows",
            format_signed_eur(
                external_flow
            ),
            "Deposits minus withdrawals",
            value_tone=external_flow,
        )

    # --------------------------------------------------------
    # Performance quality
    # --------------------------------------------------------

    st.subheader(
        "Performance quality"
    )

    quality = st.columns(6)

    with quality[0]:

        cagr = selected[
            "portfolio_cagr_pct"
        ]

        card(
            "CAGR",
            (
                format_signed_pct(
                    cagr
                )
                if not pd.isna(
                    cagr
                )
                else "N/A"
            ),
            (
                "S&amp;P "
                f"{format_signed_pct(
                    selected[
                        'benchmark_cagr_pct'
                    ]
                )}"
                if not pd.isna(
                    selected[
                        "benchmark_cagr_pct"
                    ]
                )
                else
                "Too short to annualise"
            ),
            value_tone=(
                None
                if pd.isna(cagr)
                else cagr
            ),
            compact=True,
        )

    with quality[1]:

        card(
            "Volatility",
            format_pct(
                risk_selected[
                    "annualised_volatility_pct"
                ]
            ),
            (
                "S&amp;P "
                f"{format_pct(
                    risk_selected[
                        'benchmark_volatility_pct'
                    ]
                )}"
            ),
            compact=True,
        )

    with quality[2]:

        card(
            "Beta",
            format_number(
                risk_selected[
                    "beta"
                ]
            ),
            "Market = 1.00",
            compact=True,
        )

    with quality[3]:

        card(
            "Correlation",
            format_number(
                risk_selected[
                    "correlation"
                ]
            ),
            "vs S&P 500",
            compact=True,
        )

    with quality[4]:

        card(
            "Sharpe",
            format_number(
                risk_selected[
                    "sharpe_ratio"
                ]
            ),
            compact=True,
        )

    with quality[5]:

        card(
            "Sortino",
            format_number(
                risk_selected[
                    "sortino_ratio"
                ]
            ),
            compact=True,
        )

    # --------------------------------------------------------
    # Extremes
    # --------------------------------------------------------

    extremes = (
        st.columns(4)
    )

    with extremes[0]:

        drawdown = float(
            risk_selected[
                "max_drawdown_pct"
            ]
        )

        card(
            "Max drawdown",
            format_signed_pct(
                drawdown
            ),
            (
                f"{int(
                    risk_selected[
                        'max_drawdown_duration_days'
                    ]
                )} day duration"
            ),
            value_tone=drawdown,
            compact=True,
        )

    with extremes[1]:

        best_day = float(
            selected[
                "best_day_pct"
            ]
        )

        card(
            "Best day",
            format_signed_pct(
                best_day
            ),
            value_tone=best_day,
            compact=True,
        )

    with extremes[2]:

        worst_day = float(
            selected[
                "worst_day_pct"
            ]
        )

        card(
            "Worst day",
            format_signed_pct(
                worst_day
            ),
            value_tone=worst_day,
            compact=True,
        )

    with extremes[3]:

        card(
            "Observations",
            str(
                int(
                    selected[
                        "trading_observations"
                    ]
                )
            ),
            (
                f"{int(
                    selected[
                        'calendar_days'
                    ]
                )} calendar days"
            ),
            compact=True,
        )

    # --------------------------------------------------------
    # Performance chart
    # --------------------------------------------------------

    st.subheader(
        "Portfolio vs S&P 500"
    )

    chart_start = (
        chart_first_return_date(
            history,
            selected[
                "first_date"
            ],
        )
    )

    render_growth_chart(
        history,
        first_date=chart_start,
        view="%",
        height=320,
        interaction_mode="Zoom",
        chart_key=(
            f"performance_growth_{period}"
        ),
    )

    # --------------------------------------------------------
    # Full-history perspectives
    # --------------------------------------------------------

    if period == "FULL":

        st.subheader(
            "Full-history return perspectives"
        )

        perspectives = (
            st.columns(4)
        )

        annual_xirr = float(
            returns[
                "money_weighted_return_pct"
            ]
        )

        simple_roi = float(
            performance[
                "simple_return_pct"
            ]
        )

        with perspectives[0]:

            card(
                "TWR",
                format_signed_pct(
                    portfolio_twr
                ),
                "Investment performance",
                value_tone=portfolio_twr,
            )

        with perspectives[1]:

            card(
                "Period MWR",
                format_signed_pct(
                    selected_mwr
                ),
                "Cumulative money-weighted result",
                value_tone=selected_mwr,
            )

        with perspectives[2]:

            card(
                "XIRR",
                format_signed_pct(
                    annual_xirr
                ),
                "Annualised money-weighted return",
                value_tone=annual_xirr,
            )

        with perspectives[3]:

            card(
                "Simple net-capital ROI",
                format_signed_pct(
                    simple_roi
                ),
                "Can be inflated after withdrawals",
                value_tone=simple_roi,
            )

        render_html(
            """
            <div class="section-note">
                TWR removes the effect of deposits and withdrawals.
                Money-weighted return includes their timing.
                XIRR expresses the full-history money-weighted result
                as an annualised rate. Simple ROI is included as
                context because withdrawals can shrink its denominator.
            </div>
            """
        )

    # --------------------------------------------------------
    # Compare periods
    # --------------------------------------------------------

    st.subheader(
        "Compare all periods"
    )

    comparison_rows = []

    for comparison_period in [
        "FULL",
        "1Y",
        "3M",
        "1M",
    ]:

        row = get_period_row(
            period_table,
            comparison_period,
        )

        risk_row = get_period_row(
            raw_period_table,
            comparison_period,
        )

        if row is None:
            continue

        if risk_row is None:
            risk_row = row

        comparison_rows.append(
            {
                "Period":
                    period_label(
                        comparison_period
                    ),

                "Portfolio TWR %":
                    row[
                        "portfolio_twr_pct"
                    ],

                "MWR %":
                    period_mwr_map.get(
                        comparison_period,
                        math.nan,
                    ),

                "S&P TWR %":
                    row[
                        "benchmark_twr_pct"
                    ],

                "Gap pp":
                    row[
                        "relative_return_pp"
                    ],

                "Profit EUR":
                    row[
                        "portfolio_profit_eur"
                    ],

                "External flows EUR":
                    row[
                        "external_flows_eur"
                    ],

                "Volatility %":
                    risk_row[
                        "annualised_volatility_pct"
                    ],

                "Beta":
                    risk_row[
                        "beta"
                    ],

                "Sharpe":
                    risk_row[
                        "sharpe_ratio"
                    ],

                "Max DD %":
                    risk_row[
                        "max_drawdown_pct"
                    ],

                "Best day %":
                    row[
                        "best_day_pct"
                    ],

                "Worst day %":
                    row[
                        "worst_day_pct"
                    ],
            }
        )

    comparison = pd.DataFrame(
        comparison_rows
    ).round(2)

    st.dataframe(
        comparison,
        hide_index=True,
        use_container_width=True,
    )


# ============================================================
# RISK
# ============================================================

def render_risk():

    st.title(
        "Risk"
    )

    st.caption(
        "Volatility, drawdowns, market sensitivity and position-level risk."
    )

    period = st.radio(
        "Analysis period",
        [
            "FULL",
            "1Y",
            "3M",
            "1M",
        ],
        horizontal=True,
        format_func=period_label,
        key="risk_period",
    )

    selected = get_period_row(
        raw_period_table,
        period,
    )

    if selected is None:
        return

    row1 = st.columns(4)

    with row1[0]:

        card(
            "Volatility",
            format_pct(
                selected[
                    "annualised_volatility_pct"
                ]
            ),
            (
                "S&amp;P "
                f"{format_pct(
                    selected[
                        'benchmark_volatility_pct'
                    ]
                )}"
            ),
        )

    with row1[1]:

        card(
            "Beta",
            format_number(
                selected[
                    "beta"
                ]
            ),
            "Market = 1.00",
        )

    with row1[2]:

        card(
            "Correlation",
            format_number(
                selected[
                    "correlation"
                ]
            ),
            "vs S&P 500",
        )

    with row1[3]:

        card(
            "Max drawdown",
            format_pct(
                selected[
                    "max_drawdown_pct"
                ]
            ),
            (
                f"{int(
                    selected[
                        'max_drawdown_duration_days'
                    ]
                )} day duration"
            ),
            value_tone=(
                selected[
                    "max_drawdown_pct"
                ]
            ),
        )

    row2 = st.columns(4)

    with row2[0]:

        card(
            "Sharpe",
            format_number(
                selected[
                    "sharpe_ratio"
                ]
            ),
        )

    with row2[1]:

        card(
            "Sortino",
            format_number(
                selected[
                    "sortino_ratio"
                ]
            ),
        )

    with row2[2]:

        card(
            "95% daily VaR",
            format_pct(
                selected[
                    "historical_var_pct"
                ]
            ),
        )

    with row2[3]:

        card(
            "95% daily VaR",
            format_eur(
                selected[
                    "historical_var_eur"
                ]
            ),
        )

    st.subheader(
        "Drawdown"
    )

    render_drawdown_chart(
        history,
        first_date=(
            selected[
                "first_date"
            ]
        ),
    )

    rolling_label = st.radio(
        "Rolling window",
        [
            "30 days",
            "90 days",
        ],
        horizontal=True,
        key="rolling_window",
    )

    rolling_window = (
        30
        if rolling_label
        == "30 days"
        else 90
    )

    col1, col2 = st.columns(2)

    with col1:

        st.subheader(
            "Rolling beta"
        )

        render_rolling_beta(
            history,
            rolling_window,
        )

    with col2:

        st.subheader(
            "Rolling volatility"
        )

        render_rolling_volatility(
            history,
            rolling_window,
        )

    contribution_period = st.radio(
        "Holding contribution period",
        [
            "1M",
            "3M",
            "1Y",
        ],
        index=2,
        horizontal=True,
        key="holding_risk_period",
    )

    col1, col2 = st.columns(2)

    with col1:

        st.subheader(
            "Risk contribution"
        )

        render_risk_contribution(
            holdings_table,
            contribution_period,
        )

    with col2:

        st.subheader(
            "Beta contribution"
        )

        render_beta_contribution(
            holdings_table,
            contribution_period,
        )


# ============================================================
# CAPITAL
# ============================================================

def render_capital():

    st.title(
        "Capital"
    )

    st.caption(
        "Capital contributions, withdrawals and investment profit."
    )

    peak = float(
        history[
            "net_capital_invested_eur"
        ].max()
    )

    current = float(
        history[
            "net_capital_invested_eur"
        ].iloc[-1]
    )

    removed = (
        peak
        - current
    )

    columns = st.columns(3)

    with columns[0]:

        card(
            "Peak capital",
            format_eur(
                peak
            ),
        )

    with columns[1]:

        card(
            "Current net capital",
            format_eur(
                current
            ),
        )

    with columns[2]:

        card(
            "Capital removed since peak",
            format_eur(
                removed
            ),
        )

    st.subheader(
        "Net capital invested"
    )

    render_capital_chart(
        history
    )

    st.subheader(
        "Profit history"
    )

    render_profit_chart(
        history
    )


# ============================================================
# HOLDINGS
# ============================================================

def render_holdings():

    st.title(
        "Holdings"
    )

    st.caption(
        "Current allocation, holding-level performance and risk."
    )

    st.subheader(
        "Allocation & performance"
    )

    allocation_period = st.radio(
        "Allocation return period",
        [
            "1M",
            "3M",
            "1Y",
        ],
        horizontal=True,
        key="allocation_return_period",
    )

    render_weighted_holdings_strip(
        holdings_table,
        timeframe=allocation_period,
        height=145,
    )

    st.subheader(
        "Holding performance"
    )

    holding_period = st.radio(
        "Return period",
        [
            "1M",
            "3M",
            "1Y",
        ],
        horizontal=True,
        key="holding_return_period",
    )

    render_holding_returns(
        holdings_table,
        holding_period,
    )

    st.subheader(
        "Holding statistics"
    )

    stats_period = st.radio(
        "Statistics period",
        [
            "1M",
            "3M",
            "1Y",
        ],
        index=2,
        horizontal=True,
        key="holding_stats_period",
    )

    suffix = (
        stats_period.lower()
    )

    holding_display = (
        holdings_table[
            [
                "display_ticker",
                "company",
                "current_value_eur",
                "current_weight_pct",
                f"return_{suffix}_pct",
                f"beta_{suffix}",
                f"beta_contribution_{suffix}",
                f"volatility_{suffix}_pct",
                f"correlation_{suffix}",
                f"risk_contribution_{suffix}_pct",
            ]
        ]
        .copy()
        .rename(
            columns={
                "display_ticker":
                    "Ticker",

                "company":
                    "Company",

                "current_value_eur":
                    f"Value {EURO}",

                "current_weight_pct":
                    "Weight %",

                f"return_{suffix}_pct":
                    "Return %",

                f"beta_{suffix}":
                    "Beta",

                f"beta_contribution_{suffix}":
                    "Beta Contribution",

                f"volatility_{suffix}_pct":
                    "Volatility %",

                f"correlation_{suffix}":
                    "S&P Correlation",

                f"risk_contribution_{suffix}_pct":
                    "Risk Contribution %",
            }
        )
    )

    st.dataframe(
        holding_display.round(2),
        hide_index=True,
        use_container_width=True,
    )

    st.subheader(
        "Current holdings backtest"
    )

    st.warning(
        "This is hypothetical. It holds today's portfolio "
        "weights constant through the selected historical "
        "period and is not your actual historical performance."
    )

    backtest_period = st.radio(
        "Backtest period",
        [
            "1M",
            "3M",
            "1Y",
        ],
        horizontal=True,
        key="holdings_backtest_period",
    )

    current_rows = (
        current_holdings_table[
            current_holdings_table[
                "period"
            ] == backtest_period
        ]
    )

    actual_rows = (
        raw_period_table[
            raw_period_table[
                "period"
            ] == backtest_period
        ]
    )

    if (
        not current_rows.empty
        and
        not actual_rows.empty
    ):

        current_row = (
            current_rows.iloc[0]
        )

        actual_row = (
            actual_rows.iloc[0]
        )

        columns = st.columns(4)

        with columns[0]:

            value = float(
                current_row[
                    "current_portfolio_return_pct"
                ]
            )

            card(
                "Hypothetical return",
                format_signed_pct(
                    value
                ),
                value_tone=value,
            )

        with columns[1]:

            value = float(
                current_row[
                    "benchmark_return_pct"
                ]
            )

            card(
                "S&P 500 return",
                format_signed_pct(
                    value
                ),
                value_tone=value,
            )

        with columns[2]:

            card(
                "Current holdings beta",
                format_number(
                    current_row[
                        "beta"
                    ]
                ),
                (
                    "Actual "
                    f"{format_number(
                        actual_row[
                            'beta'
                        ]
                    )}"
                ),
            )

        with columns[3]:

            card(
                "Hypothetical volatility",
                format_pct(
                    current_row[
                        "annualised_volatility_pct"
                    ]
                ),
                (
                    "Actual "
                    f"{format_pct(
                        actual_row[
                            'annualised_volatility_pct'
                        ]
                    )}"
                ),
            )


# ============================================================
# Sidebar
# ============================================================

with st.sidebar:

    render_html(
        """
        <div class="sidebar-brand">
            Portfolio Intelligence
        </div>
        """
    )

    page = st.radio(
        "Navigation",
        [
            "Overview",
            "Performance",
            "Risk",
            "Capital",
            "Holdings",
        ],
        label_visibility="collapsed",
    )

    render_html(
        """
        <div style="
            color:#59677a;
            font-size:9px;
            padding:18px 10px 0 10px;
        ">
            Trading 212 portfolio analytics
        </div>
        """
    )


# ============================================================
# Routing
# ============================================================

if page == "Overview":

    render_overview()


elif page == "Performance":

    render_performance()


elif page == "Risk":

    render_risk()


elif page == "Capital":

    render_capital()


elif page == "Holdings":

    render_holdings()