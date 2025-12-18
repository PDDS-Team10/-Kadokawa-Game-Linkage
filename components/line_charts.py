# components/line_charts.py
#
# This component provides two visualizations in the lower section of the dashboard:
#   1. A line chart showing monthly genre performance
#      based on the selected genre(s), publisher, and metric.
#   2. A bar chart showing game title performance across regions
#      for a selected genre, also based on the selected metric.
#
# Both charts:
#   - Respond to the global date range (`global-start-ym`, `global-end-ym`).
#   - Use the shared metric toggle (`metric-toggle`) to switch between
#     Revenue and Units Sold.
#
# Interaction:
#   - Users can select multiple genres and one publisher to filter the line chart.
#   - Users can select a genre to update the regional bar chart.
#   - Both charts update dynamically based on date range and metric selection.
#
# For teammates:
#   - Layout-related adjustments (spacing, sizing, titles, flex behavior) should
#     be made in `layout()`.
#
#   - To add a new trend visualization (e.g., performance by platform or region),
#     create a new figure builder and add an additional Graph component plus a
#     corresponding Output in the callback.
#
#   - To modify the data logic, update the helper functions:
#       * `_genre_publisher_trend_df()` for the line chart
#       * `_genre_bar_df()` for the bar chart

from dash import html, dcc, Input, Output, State, callback
import plotly.express as px
from utils.query import read_df
from . import genre_bar_chart

GENRE_LIST = [
    "Action", "Adventure", "Fighting", "Misc", "Platform",
    "Racing", "Role-Playing", "Shooter", "Simulation", "Sports"
]

PUBLISHER_LIST = [
    "Nintendo", "Sony Computer Entertainment", "Electronic Arts",
    "Take-Two Interactive", "Activision", "Ubisoft",
    "Microsoft Game Studios", "Bethesda Softworks"
]

LINE_PALETTE = [
    "#6C5CE7",  # 紫
    "#00B894",  # 綠
    "#0984E3",  # 藍
    "#E17055",  # 橘
    "#FD79A8",  # 粉
    "#FDCB6E",  # 黃
    "#00CEC9",  # 青
    "#2D3436",  # 深灰
    "#B33771",  # 玫紅
    "#6D214F",  # 酒紅
]

# --------- helpers ---------

def _normalize_month_range(start_ym, end_ym):
    """
    Normalize the year-month range:
    - Fill in default values if any side is missing.
    - Ensure start_ym <= end_ym by swapping if needed.

    Parameters
    ----------
    start_ym : str | None
    end_ym   : str | None

    Returns
    -------
    (start_ym, end_ym) : tuple[str, str]
        Normalized 'YYYY-MM' strings.
    """
    # 預設日期區間：2023-01 ~ 2025-12
    if not start_ym:
        start_ym = "2023-01"
    if not end_ym:
        end_ym = "2025-12"

    # 防呆：確保 start_ym <= end_ym
    if start_ym > end_ym:
        start_ym, end_ym = end_ym, start_ym

    return start_ym, end_ym


# def _genre_trend_df(start_ym, end_ym):
#     sql = """
#     SELECT 
#         m.year_month,
#         g.genre_name,
#         SUM(m.revenue_jpy) AS revenue,
#         SUM(m.sales_units)  AS units
#     FROM SaleMonthly m
#     JOIN GAME ga   ON m.game_id = ga.game_id
#     JOIN GENRE g   ON ga.genre_id = g.genre_id
#     WHERE m.year_month BETWEEN ? AND ?
#     GROUP BY m.year_month, g.genre_name
#     ORDER BY m.year_month;
#     """
#     return read_df(sql, [start_ym, end_ym])


def _genre_publisher_trend_df(start_ym, end_ym):
    sql = """
    SELECT 
        m.year_month,
        g.genre_name,
        p.publisher_name,
        SUM(m.revenue_jpy) AS revenue,
        SUM(m.sales_units)  AS units
    FROM SaleMonthly m
    JOIN GAME ga     ON m.game_id = ga.game_id
    JOIN GENRE g     ON ga.genre_id = g.genre_id
    JOIN PUBLISHER p ON ga.publisher_id = p.publisher_id
    WHERE m.year_month BETWEEN ? AND ?
    GROUP BY m.year_month, g.genre_name, p.publisher_name
    ORDER BY m.year_month;
    """
    return read_df(sql, [start_ym, end_ym])


def _build_line_fig(df, x_col, y_col, series_col, metric, title):
    """
    Shared line chart builder.
    metric: "revenue" or "units"
    """

    if df.empty:
        fig = px.line(title = title)
        fig.update_layout(
            xaxis_title = x_col,
            yaxis_title = y_col,
            margin = dict(l = 40, r = 20, t = 40, b = 40),
            plot_bgcolor = "rgba(0,0,0,0)",
            paper_bgcolor = "rgba(0,0,0,0)",
        )
        return fig

    fig = px.line(
        df,
        x = x_col,
        y = y_col,
        color = series_col,
        markers = True,
        title = None,
        template = "plotly_white",
        color_discrete_sequence = LINE_PALETTE,
    )

    unique_months = df[x_col].unique().tolist()
    tickvals = unique_months[::3] if len(unique_months) > 3 else unique_months

    fig.update_traces(
        line = dict(width = 3),
        marker = dict(size = 6),
    )

    fig.update_layout(
        plot_bgcolor = "rgba(0,0,0,0)",
        paper_bgcolor = "rgba(0,0,0,0)",
        xaxis = dict(
            title = "Month",
            tickmode = "array",
            tickvals = tickvals,
            tickangle = -45,
            showgrid = False,
        ),
        yaxis = dict(
            title = "Revenue (JPY)" if metric == "revenue" else "Units Sold",
            gridcolor = "rgba(148, 163, 184, 0.2)",
        ),
        margin = dict(l = 40, r = 20, t = 40, b = 40),
        legend = dict(
            orientation = "h",
            yanchor = "bottom",
            y = 1.02,
            xanchor = "center",
            x = 0.5,
            title_text = "",
        ),
    )
    return fig


# def _genre_trend_fig(start_ym, end_ym, metric):
#     """
#     Build the line chart for genre trend.
#     """
#     df = _genre_trend_df(start_ym, end_ym)
#     return _build_line_fig(
#         df=df,
#         x_col="year_month",
#         series_col="genre_name",
#         metric=metric,
#         title="Genre Revenue Trend" if metric == "revenue" else "Genre Units Trend",
#     )


def _genre_publisher_trend_fig(start_ym, end_ym, metric, genres, publisher):
    """
    Build the line chart for publisher trend.
    """
    df = _genre_publisher_trend_df(start_ym, end_ym)

    # ---- 過濾 genre（支援多選）----
    if genres:
        df = df[df["genre_name"].isin(genres)]

    # ---- 過濾 publisher（支援單選）----
    if publisher:
        df = df[df["publisher_name"] == publisher]

    # ---- 選擇 y 軸 ----
    y_col = "revenue" if metric == "revenue" else "units"
    y_title = "Revenue (JPY)" if metric == "revenue" else "Units Sold"

    return _build_line_fig(
        df = df,
        x_col = "year_month",
        y_col = y_col,
        series_col = "genre_name",
        metric = metric,
        title = f"{', '.join(genres)} Trend ({publisher})"
    )

def layout():
    return html.Div(
        [
            html.Div(
                [
                    html.Div(
                        [
                            html.H3(
                                "Monthly Genre Performance By Publisher",
                                style={"margin": "0 0 12px", "color": "#1e2553"},
                            ),
                            html.Div(
                                [
                                    dcc.Dropdown(
                                        id="trend-genre-select",
                                        options=[{"label": g, "value": g} for g in GENRE_LIST],
                                        multi=True,
                                        clearable=False,
                                        value=[GENRE_LIST[0]],
                                        className="pill-dropdown",
                                    ),
                                    dcc.Dropdown(
                                        id="trend-publisher-select",
                                        options=[{"label": p, "value": p} for p in PUBLISHER_LIST],
                                        multi=False,
                                        clearable=False,
                                        value="Nintendo",
                                        className="pill-dropdown",
                                        style={
                                            "minWidth": "240px",
                                            "maxWidth": "280px",
                                        },
                                    ),
                                ],
                                style={
                                    "display": "flex",
                                    "justifyContent": "center",
                                    "gap": "12px",
                                    "marginBottom": "16px",
                                },
                            ),
                            dcc.Graph(
                                id="publisher-trend-graph",
                                style={"height": "320px"},
                            ),
                        ],
                        style={
                            "display": "flex",
                            "flexDirection": "column",
                            "flex": 1,
                        },
                    ),
                    genre_bar_chart.layout(),
                ],
                style={
                    "display": "flex",
                    "flexDirection": "row",
                    "gap": "24px",
                },
            ),
        ],
        style={
            "display": "flex",
            "flexDirection": "column",
            "gap": "16px",
        },
    )


# --------- callback ---------

@callback(
    # Output("genre-trend-graph", "figure"),
    Output("publisher-trend-graph", "figure"),
    # Output("metric-display", "children"),
    Input("trend-genre-select", "value"),      # 多選 → list
    Input("trend-publisher-select", "value"),  # 單選 → list
    Input("global-start-ym", "value"),
    Input("global-end-ym", "value"),
    Input("metric-toggle", "value"), # "revenue" or "units"
    # Input("metric-toggle-temp", "value"),
)
def update_trend_charts(genres, publisher, start_ym, end_ym, metric):
    """
    Main callback for updating both trend charts.

    Flow:
    1. Normalize the date range (fill defaults and fix reversed range).
    2. Build genre trend figure based on the selected metric.
    3. Build publisher trend figure based on the same metric.
    4. Return both figures to update the two Graph components.

    In comments:
    - 若只想調整線圖樣式（顏色、字型等），可以去 `_build_line_fig()` 裡改
    """
    start_ym, end_ym = _normalize_month_range(start_ym, end_ym)

    # genre_fig = _genre_trend_fig(start_ym=start_ym, end_ym=end_ym, metric = metric_label)
    publisher_fig = _genre_publisher_trend_fig(start_ym = start_ym, end_ym = end_ym, metric = metric,
                                               genres = genres, publisher = publisher)
    return publisher_fig # , metric_label # genre_fig,


@callback(
    Output("trend-genre-select", "options"),
    Output("trend-genre-select", "value"),
    Input("trend-publisher-select", "value"),
    Input("global-start-ym", "value"),
    Input("global-end-ym", "value"),
    State("trend-genre-select", "value"),
)
def update_genre_options(publisher, start_ym, end_ym, current_value):
    start_ym, end_ym = _normalize_month_range(start_ym, end_ym)
    df = _genre_publisher_trend_df(start_ym, end_ym)

    if publisher:
        df = df[df["publisher_name"] == publisher]

    genres = sorted(df["genre_name"].unique().tolist())
    options = [{"label": g, "value": g} for g in genres]

    if not genres:
        return options, []

    if current_value is None:
        selected = []
    elif isinstance(current_value, list):
        selected = [g for g in current_value if g in genres]
    else:
        selected = [current_value] if current_value in genres else []

    if not selected:
        selected = [genres[0]]

    return options, selected


@callback(
    Output("genre-bar-select", "options"),
    Output("genre-bar-select", "value"),
    Input("trend-publisher-select", "value"),
    Input("global-start-ym", "value"),
    Input("global-end-ym", "value"),
    State("genre-bar-select", "value"),
)
def update_bar_genre_options(publisher, start_ym, end_ym, current_value):
    start_ym, end_ym = _normalize_month_range(start_ym, end_ym)
    df = _genre_publisher_trend_df(start_ym, end_ym)

    if publisher:
        df = df[df["publisher_name"] == publisher]

    genres = sorted(df["genre_name"].unique().tolist())
    options = [{"label": g, "value": g} for g in genres]

    if not genres:
        return options, None

    if current_value in genres:
        selected = current_value
    else:
        selected = genres[0]

    return options, selected
