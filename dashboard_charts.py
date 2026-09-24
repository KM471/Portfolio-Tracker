import html

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st


# ============================================================
# Design
# ============================================================

BG = "#0d1117"
PANEL = "#151b25"
BORDER = "#243042"

TEXT = "#e6ebf2"
MUTED = "#8593a8"

ACCENT = "#4c9dff"
POSITIVE = "#3fd28b"
NEGATIVE = "#ff6b7a"
BENCHMARK = "#7d8aa3"

HOLDING_PALETTE = [
    "#4c9dff",
    "#38d1c1",
    "#a78bfa",
    "#f5b455",
    "#ff7a90",
    "#7d8aa3",
]


# ============================================================
# Cleaning helpers
# ============================================================

def _clean_history(history):

    data = history.copy()

    data["date"] = pd.to_datetime(
        data["date"],
        errors="coerce",
    )

    data = (
        data
        .dropna(
            subset=["date"]
        )
        .sort_values("date")
        .drop_duplicates(
            subset=["date"],
            keep="last",
        )
        .reset_index(drop=True)
    )

    return data


def _clean_holdings(holdings):

    data = holdings.copy()

    for column in data.columns:

        if column not in [
            "ticker",
            "display_ticker",
            "company",
        ]:

            data[column] = pd.to_numeric(
                data[column],
                errors="coerce",
            )

    return data


def _history_for_period(
    history,
    first_date=None,
):

    data = _clean_history(
        history
    )

    if first_date is not None:

        first_date = pd.to_datetime(
            first_date
        )

        data = data[
            data["date"] >= first_date
        ].copy()

    return data


# ============================================================
# Plotly styling
# ============================================================

def _style_figure(
    figure,
    height=330,
):

    figure.update_layout(
        height=height,
        margin=dict(
            l=5,
            r=5,
            t=8,
            b=5,
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(
            family="Manrope, sans-serif",
            color=TEXT,
            size=11,
        ),
        hoverlabel=dict(
            bgcolor=PANEL,
            bordercolor=BORDER,
            font_color=TEXT,
            font_family="Manrope",
        ),
        xaxis=dict(
            gridcolor=BORDER,
            zerolinecolor=BORDER,
            linecolor=BORDER,
            tickfont=dict(
                color=MUTED,
            ),
            title_font=dict(
                color=MUTED,
            ),
            tickformat="%b %Y",
        ),
        yaxis=dict(
            gridcolor=BORDER,
            zerolinecolor=BORDER,
            linecolor=BORDER,
            tickfont=dict(
                color=MUTED,
            ),
            title_font=dict(
                color=MUTED,
            ),
        ),
        legend=dict(
            orientation="h",
            yanchor="top",
            y=-0.14,
            xanchor="left",
            x=0,
            font=dict(
                color=MUTED,
            ),
        ),
    )

    return figure


def _data_range(
    data,
    columns,
    padding=0.08,
):

    values = []

    for column in columns:

        if column in data.columns:

            series = pd.to_numeric(
                data[column],
                errors="coerce",
            ).dropna()

            values.extend(
                series.tolist()
            )

    if not values:
        return None

    minimum = min(values)
    maximum = max(values)

    span = maximum - minimum

    if span == 0:

        span = (
            abs(maximum)
            or 1.0
        )

    pad = (
        span
        * padding
    )

    return [
        minimum - pad,
        maximum + pad,
    ]


# ============================================================
# Selection helpers
# ============================================================

def _get_property(
    object_value,
    key,
    default=None,
):

    if object_value is None:
        return default

    if isinstance(
        object_value,
        dict,
    ):

        return object_value.get(
            key,
            default,
        )

    return getattr(
        object_value,
        key,
        default,
    )


def _extract_selected_dates(
    event,
):

    if event is None:
        return None

    selection = _get_property(
        event,
        "selection",
    )

    if selection is None:
        return None


    # First try the individual selected points.
    points = (
        _get_property(
            selection,
            "points",
            [],
        )
        or []
    )


    dates = []


    for point in points:

        date_value = _get_property(
            point,
            "x",
        )

        parsed = pd.to_datetime(
            date_value,
            errors="coerce",
        )

        if pd.notna(
            parsed
        ):

            dates.append(
                parsed
            )


    if len(dates) >= 2:

        return (
            min(dates),
            max(dates),
        )


    # Some Streamlit/Plotly versions expose the
    # selection box itself.
    boxes = (
        _get_property(
            selection,
            "box",
            [],
        )
        or []
    )


    for box in boxes:

        x_range = _get_property(
            box,
            "x",
        )

        if (
            x_range
            and len(x_range) >= 2
        ):

            start = pd.to_datetime(
                x_range[0],
                errors="coerce",
            )

            end = pd.to_datetime(
                x_range[1],
                errors="coerce",
            )

            if (
                pd.notna(start)
                and pd.notna(end)
            ):

                return (
                    min(start, end),
                    max(start, end),
                )


    return None


def _calculate_selected_period(
    data,
    start_date,
    end_date,
):

    selected = data[
        (
            data["date"]
            >= start_date
        )
        &
        (
            data["date"]
            <= end_date
        )
    ].copy()


    if len(
        selected
    ) < 2:

        return None


    first = selected.iloc[0]
    last = selected.iloc[-1]


    portfolio_start = float(
        first[
            "portfolio_growth_index"
        ]
    )

    portfolio_end = float(
        last[
            "portfolio_growth_index"
        ]
    )


    benchmark_start = float(
        first[
            "benchmark_growth_index"
        ]
    )

    benchmark_end = float(
        last[
            "benchmark_growth_index"
        ]
    )


    if (
        portfolio_start == 0
        or benchmark_start == 0
    ):

        return None


    portfolio_return = (
        (
            portfolio_end
            /
            portfolio_start
        )
        - 1
    ) * 100


    benchmark_return = (
        (
            benchmark_end
            /
            benchmark_start
        )
        - 1
    ) * 100


    return {
        "start_date":
            first["date"],

        "end_date":
            last["date"],

        "portfolio_return_pct":
            portfolio_return,

        "benchmark_return_pct":
            benchmark_return,

        "gap_pp":
            (
                portfolio_return
                -
                benchmark_return
            ),
    }


# ============================================================
# Growth chart
# ============================================================

def render_growth_chart(
    history,
    first_date=None,
    view="%",
    height=285,
    interaction_mode="Zoom",
    chart_key="growth_chart",
):

    data = _history_for_period(
        history,
        first_date,
    )


    if data.empty:

        st.info(
            "No performance history available."
        )

        return None


    start_date = data[
        "date"
    ].min()

    end_date = data[
        "date"
    ].max()


    figure = go.Figure()


    # --------------------------------------------------------
    # Percentage view
    # --------------------------------------------------------

    if view == "%":

        portfolio_returns = pd.to_numeric(
            data[
                "portfolio_daily_return"
            ],
            errors="coerce",
        ).fillna(
            0.0
        )


        benchmark_returns = pd.to_numeric(
            data[
                "benchmark_daily_return"
            ],
            errors="coerce",
        ).fillna(
            0.0
        )


        if len(
            portfolio_returns
        ) > 0:

            portfolio_returns.iloc[
                0
            ] = 0.0

            benchmark_returns.iloc[
                0
            ] = 0.0


        data[
            "portfolio_period_return"
        ] = (
            (
                1
                + portfolio_returns
            )
            .cumprod()
            - 1
        ) * 100


        data[
            "benchmark_period_return"
        ] = (
            (
                1
                + benchmark_returns
            )
            .cumprod()
            - 1
        ) * 100


        data[
            "performance_gap_pp"
        ] = (
            data[
                "portfolio_period_return"
            ]
            -
            data[
                "benchmark_period_return"
            ]
        )


        custom_data = np.column_stack(
            [
                data[
                    "benchmark_period_return"
                ],
                data[
                    "performance_gap_pp"
                ],
            ]
        )


        # Invisible markers are included so box selection
        # has concrete points to select.
        figure.add_trace(
            go.Scatter(
                x=data["date"],
                y=data[
                    "portfolio_period_return"
                ],
                customdata=custom_data,
                mode="lines+markers",
                name="Portfolio",
                line=dict(
                    color=ACCENT,
                    width=2.4,
                ),
                marker=dict(
                    size=6,
                    opacity=0.01,
                    color=ACCENT,
                ),
                fill="tozeroy",
                fillcolor=(
                    "rgba(76,157,255,0.07)"
                ),
                hovertemplate=(
                    "<b>%{x|%d %b %Y}</b>"
                    "<br>Portfolio: %{y:+.2f}%"
                    "<br>S&P 500: %{customdata[0]:+.2f}%"
                    "<br>Gap: %{customdata[1]:+.2f} pp"
                    "<extra></extra>"
                ),
            )
        )


        figure.add_trace(
            go.Scatter(
                x=data["date"],
                y=data[
                    "benchmark_period_return"
                ],
                mode="lines+markers",
                name="S&P 500",
                line=dict(
                    color=BENCHMARK,
                    width=1.8,
                ),
                marker=dict(
                    size=6,
                    opacity=0.01,
                    color=BENCHMARK,
                ),
                hovertemplate=(
                    "S&P 500: %{y:+.2f}%"
                    "<extra></extra>"
                ),
            )
        )


        figure.update_yaxes(
            title="Return %",
            ticksuffix="%",
            range=_data_range(
                data,
                [
                    "portfolio_period_return",
                    "benchmark_period_return",
                ],
            ),
        )


    # --------------------------------------------------------
    # Euro view
    # --------------------------------------------------------

    else:

        euro_gap = (
            data[
                "portfolio_value_eur"
            ]
            -
            data[
                "benchmark_value_eur"
            ]
        )


        custom_data = np.column_stack(
            [
                data[
                    "benchmark_value_eur"
                ],
                euro_gap,
            ]
        )


        figure.add_trace(
            go.Scatter(
                x=data["date"],
                y=data[
                    "portfolio_value_eur"
                ],
                customdata=custom_data,
                mode="lines+markers",
                name="Portfolio",
                line=dict(
                    color=ACCENT,
                    width=2.4,
                ),
                marker=dict(
                    size=6,
                    opacity=0.01,
                    color=ACCENT,
                ),
                fill="tozeroy",
                fillcolor=(
                    "rgba(76,157,255,0.07)"
                ),
                hovertemplate=(
                    "<b>%{x|%d %b %Y}</b>"
                    "<br>Portfolio: €%{y:,.2f}"
                    "<br>S&P 500: €%{customdata[0]:,.2f}"
                    "<br>Gap: €%{customdata[1]:+,.2f}"
                    "<extra></extra>"
                ),
            )
        )


        figure.add_trace(
            go.Scatter(
                x=data["date"],
                y=data[
                    "benchmark_value_eur"
                ],
                mode="lines+markers",
                name="S&P 500",
                line=dict(
                    color=BENCHMARK,
                    width=1.8,
                ),
                marker=dict(
                    size=6,
                    opacity=0.01,
                    color=BENCHMARK,
                ),
                hovertemplate=(
                    "S&P 500: €%{y:,.2f}"
                    "<extra></extra>"
                ),
            )
        )


        figure.update_yaxes(
            title="Value €",
            tickprefix="€",
            range=_data_range(
                data,
                [
                    "portfolio_value_eur",
                    "benchmark_value_eur",
                ],
            ),
        )


    # --------------------------------------------------------
    # Shared interaction
    # --------------------------------------------------------

    figure.update_xaxes(
        range=[
            start_date,
            end_date,
        ],
        showspikes=True,
        spikecolor="#44546a",
        spikethickness=1,
        spikedash="dot",
        spikesnap="cursor",
    )


    figure.update_layout(
        hovermode="x unified",
        dragmode=(
            "select"
            if interaction_mode
            == "Measure"
            else
            "zoom"
        ),
    )


    figure = _style_figure(
        figure,
        height=height,
    )


    if (
        interaction_mode
        == "Measure"
    ):

        config = {
            "displayModeBar":
                "hover",

            "displaylogo":
                False,

            "scrollZoom":
                False,

            "doubleClick":
                False,

            "modeBarButtonsToRemove":
                [
                    "toImage",
                    "lasso2d",
                    "pan2d",
                    "zoom2d",
                    "zoomIn2d",
                    "zoomOut2d",
                    "autoScale2d",
                ],
        }


        event = st.plotly_chart(
            figure,
            use_container_width=True,
            key=chart_key,
            on_select="rerun",
            selection_mode="box",
            config=config,
        )


        selected_range = (
            _extract_selected_dates(
                event
            )
        )


        if selected_range is None:
            return None


        return _calculate_selected_period(
            data,
            selected_range[0],
            selected_range[1],
        )


    config = {
        "displayModeBar":
            "hover",

        "displaylogo":
            False,

        "scrollZoom":
            True,

        "doubleClick":
            False,

        "modeBarButtonsToRemove":
            [
                "toImage",
                "lasso2d",
                "select2d",
                "pan2d",
                "autoScale2d",
            ],
    }


    st.plotly_chart(
        figure,
        use_container_width=True,
        key=chart_key,
        config=config,
    )


    return None


# ============================================================
# Allocation donut
# ============================================================

def render_allocation_donut(
    holdings,
    height=250,
):

    data = _clean_holdings(
        holdings
    )


    data = (
        data[
            data[
                "current_weight_pct"
            ] >= 0.1
        ]
        .sort_values(
            "current_weight_pct",
            ascending=False,
        )
        .copy()
    )


    if data.empty:

        st.info(
            "No allocation data available."
        )

        return


    legend_labels = [
        (
            f"{row['display_ticker']} "
            f"{row['current_weight_pct']:.1f}%"
        )
        for _, row
        in data.iterrows()
    ]


    figure = go.Figure(
        go.Pie(
            labels=legend_labels,
            values=data[
                "current_weight_pct"
            ],
            customdata=data[
                "display_ticker"
            ],
            hole=0.66,
            sort=False,
            text=[
                (
                    f"{weight:.0f}%"
                )
                for weight
                in data[
                    "current_weight_pct"
                ]
            ],
            textinfo="text",
            textposition="inside",
            insidetextorientation=(
                "horizontal"
            ),
            textfont=dict(
                size=11,
                color=TEXT,
            ),
            marker=dict(
                colors=HOLDING_PALETTE,
                line=dict(
                    color=BG,
                    width=2,
                ),
            ),
            hovertemplate=(
                "<b>%{customdata}</b>"
                "<br>Weight: %{value:.2f}%"
                "<extra></extra>"
            ),
        )
    )


    figure.update_layout(
        height=height,
        margin=dict(
            l=0,
            r=0,
            t=0,
            b=34,
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(
            family="Manrope",
            color=TEXT,
        ),
        legend=dict(
            orientation="h",
            y=-0.04,
            x=0.5,
            xanchor="center",
            font=dict(
                size=9,
                color=MUTED,
            ),
        ),
    )


    st.plotly_chart(
        figure,
        use_container_width=True,
        config={
            "displayModeBar":
                False,
        },
    )


# ============================================================
# Weighted holdings strip
# ============================================================

def _holding_return_column(
    data,
    timeframe,
):

    if timeframe == "1M":

        return (
            "return_1m_pct",
            "1-month return",
        )


    if timeframe == "3M":

        return (
            "return_3m_pct",
            "3-month return",
        )


    if timeframe == "1Y":

        return (
            "return_1y_pct",
            "1-year return",
        )


    cost_basis = (
        data[
            "current_value_eur"
        ]
        -
        data[
            "unrealised_pnl"
        ]
    )


    data[
        "return_since_purchase_pct"
    ] = np.where(
        cost_basis > 0,
        (
            data[
                "unrealised_pnl"
            ]
            /
            cost_basis
        )
        * 100,
        np.nan,
    )


    return (
        "return_since_purchase_pct",
        "return since purchase",
    )


def _tile_colour(
    value,
    max_abs,
):

    if pd.isna(
        value
    ):

        return (
            "rgba(125,138,163,0.30)"
        )


    intensity = (
        min(
            abs(
                float(value)
            )
            /
            max_abs,
            1.0,
        )
        if max_abs > 0
        else 0
    )


    alpha = (
        0.30
        +
        intensity
        * 0.52
    )


    if value > 0:

        return (
            f"rgba(63,210,139,{alpha:.2f})"
        )


    if value < 0:

        return (
            f"rgba(255,107,122,{alpha:.2f})"
        )


    return (
        "rgba(125,138,163,0.30)"
    )


def render_weighted_holdings_strip(
    holdings,
    timeframe="1M",
    height=135,
):

    data = _clean_holdings(
        holdings
    )


    data = data[
        data[
            "current_weight_pct"
        ] >= 0.1
    ].copy()


    (
        return_column,
        return_label,
    ) = _holding_return_column(
        data,
        timeframe,
    )


    data = (
        data
        .dropna(
            subset=[
                "display_ticker",
                "current_weight_pct",
                return_column,
            ]
        )
        .sort_values(
            "current_weight_pct",
            ascending=False,
        )
    )


    if data.empty:

        st.info(
            "No holding return data available."
        )

        return


    max_abs = max(
        data[
            return_column
        ]
        .abs()
        .max(),
        1.0,
    )


    tiles = []


    for _, row in data.iterrows():

        ticker = html.escape(
            str(
                row[
                    "display_ticker"
                ]
            )
        )


        weight = float(
            row[
                "current_weight_pct"
            ]
        )


        holding_return = float(
            row[
                return_column
            ]
        )


        colour = _tile_colour(
            holding_return,
            max_abs,
        )


        tiles.append(
            f"""
            <div
                style="
                    flex:{max(weight, 5):.2f} 1 0;
                    min-width:74px;
                    height:{height}px;
                    background:{colour};
                    border:1px solid rgba(255,255,255,0.04);
                    border-radius:13px;
                    padding:13px 12px;
                    box-sizing:border-box;
                    display:flex;
                    flex-direction:column;
                    justify-content:space-between;
                    overflow:hidden;
                "
            >
                <div
                    style="
                        color:#e6ebf2;
                        font-size:16px;
                        font-weight:800;
                        letter-spacing:-0.3px;
                    "
                >
                    {ticker}
                </div>

                <div
                    style="
                        color:#e6ebf2;
                        font-size:12px;
                        font-weight:650;
                        line-height:1.35;
                    "
                >
                    {weight:.0f}% · {holding_return:+.2f}%
                </div>
            </div>
            """
        )


    markup = f"""
    <div
        style="
            background:#111a17;
            border:1px solid #24382f;
            border-radius:14px;
            padding:15px;
        "
    >

        <div
            style="
                color:#8593a8;
                font-size:11px;
                margin-bottom:10px;
            "
        >
            Holdings sized by current weight · coloured by {return_label}
        </div>

        <div
            style="
                display:flex;
                gap:8px;
                width:100%;
            "
        >
            {''.join(tiles)}
        </div>

    </div>
    """


    st.html(
        markup
    )


# ============================================================
# Capital
# ============================================================

def render_capital_chart(
    history,
):

    data = _clean_history(
        history
    )


    figure = go.Figure()


    figure.add_trace(
        go.Scatter(
            x=data["date"],
            y=data[
                "net_capital_invested_eur"
            ],
            mode="lines",
            line=dict(
                color=ACCENT,
                width=2.4,
            ),
            fill="tozeroy",
            fillcolor=(
                "rgba(76,157,255,0.07)"
            ),
            hovertemplate=(
                "<b>%{x|%d %b %Y}</b>"
                "<br>Net capital: €%{y:,.2f}"
                "<extra></extra>"
            ),
        )
    )


    figure = _style_figure(
        figure,
        350,
    )


    figure.update_xaxes(
        range=[
            data["date"].min(),
            data["date"].max(),
        ]
    )


    figure.update_yaxes(
        title="EUR",
        tickprefix="€",
    )


    st.plotly_chart(
        figure,
        use_container_width=True,
        config={
            "displayModeBar":
                False,
        },
    )


def render_profit_chart(
    history,
):

    data = _clean_history(
        history
    )


    data[
        "simple_gain_eur"
    ] = (
        pd.to_numeric(
            data[
                "simple_gain_eur"
            ],
            errors="coerce",
        )
        .ffill()
    )


    figure = go.Figure()


    figure.add_trace(
        go.Scatter(
            x=data["date"],
            y=data[
                "simple_gain_eur"
            ],
            mode="lines",
            line=dict(
                color=POSITIVE,
                width=2.4,
            ),
            fill="tozeroy",
            fillcolor=(
                "rgba(63,210,139,0.06)"
            ),
            hovertemplate=(
                "<b>%{x|%d %b %Y}</b>"
                "<br>Profit: €%{y:+,.2f}"
                "<extra></extra>"
            ),
        )
    )


    figure = _style_figure(
        figure,
        350,
    )


    figure.update_xaxes(
        range=[
            data["date"].min(),
            data["date"].max(),
        ]
    )


    figure.update_yaxes(
        title="EUR",
        tickprefix="€",
    )


    st.plotly_chart(
        figure,
        use_container_width=True,
        config={
            "displayModeBar":
                False,
        },
    )


# ============================================================
# Drawdown
# ============================================================

def render_drawdown_chart(
    history,
    first_date=None,
):

    data = _history_for_period(
        history,
        first_date,
    )


    if data.empty:
        return


    figure = go.Figure()


    figure.add_trace(
        go.Scatter(
            x=data["date"],
            y=data[
                "portfolio_drawdown_pct"
            ],
            mode="lines",
            name="Portfolio",
            line=dict(
                color=NEGATIVE,
                width=2.2,
            ),
            fill="tozeroy",
            fillcolor=(
                "rgba(255,107,122,0.07)"
            ),
        )
    )


    figure.add_trace(
        go.Scatter(
            x=data["date"],
            y=data[
                "benchmark_drawdown_pct"
            ],
            mode="lines",
            name="S&P 500",
            line=dict(
                color=BENCHMARK,
                width=1.8,
            ),
        )
    )


    figure = _style_figure(
        figure,
        340,
    )


    figure.update_layout(
        hovermode="x unified",
    )


    figure.update_xaxes(
        range=[
            data["date"].min(),
            data["date"].max(),
        ]
    )


    figure.update_yaxes(
        title="Drawdown %",
        ticksuffix="%",
    )


    st.plotly_chart(
        figure,
        use_container_width=True,
        config={
            "displayModeBar":
                False,
        },
    )


# ============================================================
# Rolling risk
# ============================================================

def _rolling_risk_data(
    history,
    window,
):

    data = _clean_history(
        history
    )


    portfolio = pd.to_numeric(
        data[
            "portfolio_daily_return"
        ],
        errors="coerce",
    )


    benchmark = pd.to_numeric(
        data[
            "benchmark_daily_return"
        ],
        errors="coerce",
    )


    data[
        "rolling_volatility_pct"
    ] = (
        portfolio
        .rolling(
            window,
            min_periods=window,
        )
        .std()
        * np.sqrt(252)
        * 100
    )


    covariance = (
        portfolio
        .rolling(
            window,
            min_periods=window,
        )
        .cov(
            benchmark
        )
    )


    benchmark_variance = (
        benchmark
        .rolling(
            window,
            min_periods=window,
        )
        .var()
    )


    data[
        "rolling_beta"
    ] = (
        covariance
        /
        benchmark_variance
    )


    return data


def render_rolling_beta(
    history,
    window=30,
):

    data = _rolling_risk_data(
        history,
        window,
    )


    figure = go.Figure()


    figure.add_trace(
        go.Scatter(
            x=data["date"],
            y=data[
                "rolling_beta"
            ],
            mode="lines",
            line=dict(
                color=ACCENT,
                width=2,
            ),
        )
    )


    figure.add_hline(
        y=1.0,
        line=dict(
            color=BENCHMARK,
            dash="dash",
            width=1,
        ),
    )


    figure = _style_figure(
        figure,
        310,
    )


    figure.update_xaxes(
        range=[
            data["date"].min(),
            data["date"].max(),
        ]
    )


    st.plotly_chart(
        figure,
        use_container_width=True,
        config={
            "displayModeBar":
                False,
        },
    )


def render_rolling_volatility(
    history,
    window=30,
):

    data = _rolling_risk_data(
        history,
        window,
    )


    figure = go.Figure()


    figure.add_trace(
        go.Scatter(
            x=data["date"],
            y=data[
                "rolling_volatility_pct"
            ],
            mode="lines",
            line=dict(
                color="#a78bfa",
                width=2,
            ),
        )
    )


    figure = _style_figure(
        figure,
        310,
    )


    figure.update_xaxes(
        range=[
            data["date"].min(),
            data["date"].max(),
        ]
    )


    figure.update_yaxes(
        ticksuffix="%",
    )


    st.plotly_chart(
        figure,
        use_container_width=True,
        config={
            "displayModeBar":
                False,
        },
    )


# ============================================================
# Holdings
# ============================================================

def render_holding_returns(
    holdings,
    period="1M",
):

    data = _clean_holdings(
        holdings
    )


    column = {
        "1M":
            "return_1m_pct",
        "3M":
            "return_3m_pct",
        "1Y":
            "return_1y_pct",
    }[
        period
    ]


    data = (
        data[
            [
                "display_ticker",
                column,
            ]
        ]
        .dropna()
        .sort_values(
            column,
            ascending=True,
        )
    )


    colours = np.where(
        data[column] >= 0,
        POSITIVE,
        NEGATIVE,
    )


    figure = go.Figure(
        go.Bar(
            x=data[column],
            y=data[
                "display_ticker"
            ],
            orientation="h",
            marker_color=colours,
            hovertemplate=(
                "<b>%{y}</b>"
                "<br>%{x:+.2f}%"
                "<extra></extra>"
            ),
        )
    )


    figure = _style_figure(
        figure,
        340,
    )


    figure.update_xaxes(
        title="Return %",
        ticksuffix="%",
        zeroline=True,
        zerolinecolor=BORDER,
    )


    figure.update_yaxes(
        title="",
        gridcolor="rgba(0,0,0,0)",
    )


    st.plotly_chart(
        figure,
        use_container_width=True,
        config={
            "displayModeBar":
                False,
        },
    )


def render_beta_contribution(
    holdings,
    period="1Y",
):

    data = _clean_holdings(
        holdings
    )


    column = {
        "1M":
            "beta_contribution_1m",
        "3M":
            "beta_contribution_3m",
        "1Y":
            "beta_contribution_1y",
    }[
        period
    ]


    data = (
        data[
            [
                "display_ticker",
                column,
            ]
        ]
        .dropna()
        .sort_values(
            column,
            ascending=True,
        )
    )


    figure = go.Figure(
        go.Bar(
            x=data[column],
            y=data[
                "display_ticker"
            ],
            orientation="h",
            marker_color=ACCENT,
        )
    )


    figure = _style_figure(
        figure,
        340,
    )


    st.plotly_chart(
        figure,
        use_container_width=True,
        config={
            "displayModeBar":
                False,
        },
    )


def render_risk_contribution(
    holdings,
    period="1Y",
):

    data = _clean_holdings(
        holdings
    )


    column = {
        "1M":
            "risk_contribution_1m_pct",
        "3M":
            "risk_contribution_3m_pct",
        "1Y":
            "risk_contribution_1y_pct",
    }[
        period
    ]


    data = (
        data[
            [
                "display_ticker",
                column,
            ]
        ]
        .dropna()
        .sort_values(
            column,
            ascending=True,
        )
    )


    colours = np.where(
        data[column] >= 0,
        NEGATIVE,
        POSITIVE,
    )


    figure = go.Figure(
        go.Bar(
            x=data[column],
            y=data[
                "display_ticker"
            ],
            orientation="h",
            marker_color=colours,
        )
    )


    figure = _style_figure(
        figure,
        340,
    )


    figure.update_xaxes(
        ticksuffix="%",
    )


    st.plotly_chart(
        figure,
        use_container_width=True,
        config={
            "displayModeBar":
                False,
        },
    )