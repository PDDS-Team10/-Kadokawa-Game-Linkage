# components/line_charts.py
#
# This component shows two line charts in the middle section of the dashboard:
#   - Genre trend over time
#   - Publisher trend over time
#
# Both charts:
#   - Use the global year-month filters (`global-start-ym`, `global-end-ym`).
#   - Share the same metric toggle: "Revenue" or "Units Sold".
#
# For teammates (especially front-end):
# - If you want to change layout (e.g., height, titles, flex layout),
#   you can usually do it inside `layout()`.
# - If you want to add a new trend chart (e.g., by Platform),
#   you can copy `_genre_trend_df` / `_genre_trend_fig` as a template and
#   add a new Graph + one more Output in `update_trend_charts`.

from dash import html, dcc, Input, Output, callback
import plotly.express as px
import dash_daq as daq
from utils.query import read_df

GENRE_LIST = [
    "Action", "Adventure", "Fighting", "Misc", "Platform",
    "Racing", "Role-Playing", "Shooter", "Simulation", "Sports"
]

PUBLISHER_LIST = [
    "Nintendo", "Sony Computer Entertainment", "Electronic Arts",
    "Take-Two Interactive", "Activision", "Ubisoft",
    "Microsoft Game Studios", "Bethesda Softworks"
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
    # 預設日期區間：2022-01 ~ 2024-12
    if not start_ym:
        start_ym = "2022-01"
    if not end_ym:
        end_ym = "2024-12"

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

    # 沒有資料時：空圖，保留標題與 margin
    if df.empty:
        fig = px.line(title = title)
        fig.update_layout(
            xaxis_title = x_col,
            yaxis_title = y_col,
            margin = dict(l = 40, r = 10, t = 40, b = 80),
        )
        return fig

    # 選擇 y 軸欄位與標籤
    # if metric == "units":
    #     y_col = "units"
    #     y_title = "Units Sold"
    # else:
    #     y_col = "revenue"
    #     y_title = "Revenue (JPY)"

    fig = px.line(
        df,
        x = x_col,
        y = y_col,
        color = series_col,
        markers = True, # 每個點加 marker 方便讀值
        title = title,
    )

    # X 軸顯示每 3 個月一個刻度(避免字太擠)
    # 這個可以再調整
    unique_months = df[x_col].unique().tolist()
    tickvals = unique_months[::3] if len(unique_months) > 3 else unique_months

    fig.update_layout(
        xaxis_title = x_col,
        yaxis_title = y_col,
        margin = dict(l = 20, r = 20, t = 60, b = 20), # 上方留空給標題
        xaxis = dict(
            tickmode = "array",
            tickvals = tickvals,
            tickangle = -45,
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


# --------- layout ---------

def layout():
    """
    Layout for the trend section.

    Contains:
    - Title + metric toggle (Revenue / Units Sold).
    - Two side-by-side graphs:
        - Left: Genre trend
        - Right: Publisher trend

    In comments:
    - 想調整高度、邊距、標題文字，可以直接改這裡的 style 或 H3/H4 文案。
    """
    return html.Div(
        [
            # 標題 + Metric 切換
            html.Div(
                [
                    html.H3("Monthly Genre Performance By Publisher", style = {"margin": "0", "marginRight": "16px"}), # 讓 Metric 靠近

                    # Dropdown 列（Genre 多選 + Publisher 單選）
                    html.Div(
                        [
                            # Genre Selector
                            html.Div(
                                [
                                    dcc.Dropdown(
                                        id = "trend-genre-select",
                                        options = [{"label": g, "value": g} for g in GENRE_LIST],
                                        multi = True,
                                        placeholder = "Select Genre(s)",
                                        value = ["Action"],   # 預設
                                        className = "trend-dropdown"
                                    )
                                ],
                                style = {"flex": 1, "marginRight": "12px"},
                            ),

                            # Publisher Selector
                            html.Div(
                                [
                                    dcc.Dropdown(
                                        id = "trend-publisher-select",
                                        options = [{"label": p, "value": p} for p in PUBLISHER_LIST],
                                        multi = False,
                                        placeholder = "Select Publisher",
                                        value = "Nintendo",   # 預設
                                        className = "trend-dropdown"
                                    )
                                ],
                                style = {"flex": 1},
                            ),
                        ],
                        style = {
                            "display": "flex",
                            "flexDirection": "row",
                            "marginBottom": "16px",
                        },
                    ),

                    # html.Div(
                    #     [
                            # html.Span("Metric:", style ={"marginRight": "6px"}),

                            # daq.ToggleSwitch(
                            #     id = "metric-toggle-temp",
                            #     # label = "Metric",
                            #     value = False,  # False = Revenue, True = Units
                            #     labelPosition = "right",
                            #     style = {"marginTop": "4px"}
                            # ),

                            # html.Div(id = "metric-display", style = {"marginLeft": "8px"})  # 可用來動態顯示當前 Metric

                            # dcc.RadioItems(
                            #     id="trend-metric-toggle",
                            #     options=[
                            #         {"label": "Revenue", "value": "revenue"},
                            #         {"label": "Units Sold", "value": "units"},
                            #     ],
                            #     value="revenue",
                            #     inline=True,
                            # ),
                    #     ],
                    #     style={
                    #         "display": "flex",
                    #         "alignItems": "center"
                    #     },
                    # ),
                ],
                style={
                    "display": "flex",
                    "alignItems": "center",
                    "marginBottom": "8px",
                },
            ),

            # 兩張圖
            html.Div(
                [
                    html.Div(
                        [
                            html.H4(
                                style={"marginBottom": "4px"},
                            ),
                            dcc.Graph(
                                id="publisher-trend-graph",
                                style={"height": "360px"},
                            ),
                        ],
                        style={"flex": "1"},
                    ),
                    # html.Div(
                    #     [
                    #         dcc.Graph(
                    #             id="genre-trend-graph",
                    #             style={"height": "360px"},
                    #         ),
                    #     ],
                    #     style={"flex": "1", "marginRight": "16px"},
                    # ),
                ],
                style={
                    "display": "flex",
                    "flexDirection": "row",
                    "marginBottom": "16px",
                },
            ),
        ]
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

