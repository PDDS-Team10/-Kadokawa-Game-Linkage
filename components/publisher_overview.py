# components/publisher_overview.py
#
# Publisher Overview section
#
# This component displays two coordinated visualizations:
#   1. A treemap showing the Top 5 or Worst 5 publishers,
#      based on either revenue or units sold.
#   2. A pie chart breaking down the selected publisher’s game-level revenue
#      or units sold.
#
# Interaction:
#   - The "Top 5" and "Worst 5" buttons switch the ranking mode used in the treemap.
#   - Clicking a publisher in the treemap updates the pie chart to show
#     that publisher’s top titles.
#   - The global date range (`global-start-ym`, `global-end-ym`) filters both charts.
#   - The metric toggle (`metric-toggle`) switches all calculations and color scales
#     between revenue and units sold.
#   - Clicking inside the treemap also triggers zoom-in/zoom-out interactions
#     provided by Plotly.
#
# For teammates:
#   - To adjust visual styling (layout spacing, colors, height), edit `layout()`
#     or the figure builder functions `_publisher_treemap()` and
#     `_publisher_games_pie()`.
#
#   - To modify ranking logic for Top/Worst 5, update `_publisher_df()` and the
#     logic in `update_publisher_overview()` that determines the `order` and
#     `mode_label` values.
#
#   - If new metrics are needed in the future, extend `_publisher_df()` and ensure
#     the treemap and pie chart functions read from the appropriate column.

import pandas as pd
from dash import html, dcc, Input, Output, callback, ctx, no_update, State
import plotly.express as px
from utils.query import read_df
from components.kpi_cards import _format_compact_number

# ---------- helpers ----------

def _normalize_month_range(start_ym, end_ym):
    if not start_ym:
        start_ym = "2023-01"
    if not end_ym:
        end_ym = "2025-12"
    if start_ym > end_ym:
        start_ym, end_ym = end_ym, start_ym
    return start_ym, end_ym


def _publisher_df(start_ym = "2023-01", end_ym = "2025-12"): # order = "ASC", limit = 5, 
    sql = f"""
    SELECT 
        p.publisher_name,
        SUM(m.revenue_jpy) AS revenue,  
        SUM(m.sales_units)  AS units
    FROM SaleMonthly m
    JOIN GAME g      ON m.game_id = g.game_id
    JOIN PUBLISHER p ON g.publisher_id = p.publisher_id
    WHERE m.year_month BETWEEN ? AND ?
    GROUP BY p.publisher_name;
    """
    # ORDER BY revenue {order}
    # LIMIT ?;
    return read_df(sql, [start_ym, end_ym]) # , limit


def _publisher_treemap(df, mode_label, metric = "revenue"):
    """
    Build the treemap for publishers.

    - The rectangle size is based on sqrt(revenue) to reduce extreme skew.
    - Color is still mapped to raw revenue.
    """
    df = df.copy()

    # 調整要顯示的欄位
    metric_col = "revenue" if metric == "revenue" else "units"

    df["area_value"] = (df[metric_col].clip(lower = 0) ** 0.5)

    # 排序方式（Top = DESC, Worst = ASC）
    ascending = (mode_label == "Worst")
    df = df.sort_values(metric_col, ascending = ascending).head()

    # # 排序確保 Top/Worst 左上位置正確
    # if mode_label == "Top":
    #     df = df.sort_values("revenue", ascending = False)
    # else:  # Worst
    #     df = df.sort_values("revenue", ascending = True)

    title_metric = "Revenue" if metric == "revenue" else "Units Sold"

    fig = px.treemap(
        df,
        path = ["publisher_name"],
        values = "area_value",
        color = metric_col,
        color_continuous_scale = "Blues",
        title = f"{mode_label} 5 Publishers by {title_metric}",
    )

    df[metric_col] = df[metric_col].apply(lambda x: _format_compact_number(x))

    # Custom hover text to show nicely formatted revenue
    fig.update_traces(
        customdata = df[["publisher_name", metric_col]].to_numpy(),
        hovertemplate = "<b>%{label}</b><br>"
                        f"{title_metric}: " 
                        "%{customdata[1]}"
                        "<extra></extra>",
        marker = dict(line = dict(width = 0, color = "rgba(0,0,0,0)")),
    )

    fig.update_layout(
        margin = dict(l = 0, r = 10, t = 70, b = 10),
        height = 380,
        title_x = 0,
        clickmode = "event+select",
        paper_bgcolor = "rgba(0,0,0,0)",
        plot_bgcolor = "rgba(0,0,0,0)",
        uirevision = "publisher-treemap"
    )
    return fig


def _games_df_for_publisher(publisher_name, start_ym = "2023-01", end_ym = "2025-12"):
    sql = """
    SELECT 
        g.game_name,
        SUM(m.revenue_jpy) AS revenue,
        SUM(m.sales_units) AS units
    FROM SaleMonthly m
    JOIN GAME g      ON m.game_id = g.game_id
    JOIN PUBLISHER p ON g.publisher_id = p.publisher_id
    WHERE p.publisher_name = ?
      AND m.year_month BETWEEN ? AND ?
    GROUP BY g.game_name
    ORDER BY revenue DESC;
    """
    return read_df(sql, [publisher_name, start_ym, end_ym])

def _top3_with_others(df, value_col = "revenue"):
    """
    df: game_name, revenue (或 units)
    value_col: "revenue" 或 "units"
    """

    # 排序
    df_sorted = df.sort_values(value_col, ascending = False)

    if len(df_sorted) <= 3:
        return df_sorted  # 不需要合併 Others

    # Top 3
    top3 = df_sorted.iloc[:3].copy()

    # Others
    others_value = df_sorted.iloc[3:][value_col].sum()

    others_row = pd.DataFrame([{
        "game_name": "Others",
        value_col: others_value
    }])

    # 合併成正式資料
    final_df = pd.concat([top3, others_row], ignore_index = True)

    return final_df

def _empty_pie_placeholder(message = "Select a publisher from treemap"):
    """
    Build a placeholder pie chart when there is no selection or no data.
    """
    placeholder_colors = ["#264a7f"]
    fig = px.pie(
        names = ["No selection"],
        values = [1],
        title = message,
        color_discrete_sequence = placeholder_colors,
    )
    fig.update_layout(
        showlegend = False,
        margin = dict(l = 10, r = 10, t = 40, b = 10),
        height = 380,
    )
    return fig

def _publisher_games_pie(publisher_name, start_ym, end_ym, metric = "revenue"):
    """
    Build the pie chart for one publisher's game revenue share.
    """
    df = _games_df_for_publisher(publisher_name, start_ym = start_ym, end_ym = end_ym)

    if df.empty:
        return _empty_pie_placeholder(f"{publisher_name}: no game data", metric = metric)
    
    df_top = _top3_with_others(df, value_col = metric)

    # 加 custom_data 以便 hover 顯示 value
    df_top["formatted_value"] = df_top[metric].apply(lambda x: _format_compact_number(x))

    custom_colors = ['#264a7f', '#5d85b3', '#a5c0dd', '#dce6f2']  # 深 → 淺

    fig = px.pie(
        df_top,
        names = "game_name",
        values = metric,
        color = "game_name",
        color_discrete_sequence = custom_colors,
        hole = 0.55,
    )

    label_name = "Revenue" if metric == "revenue" else "Units Sold"

    fig.update_traces(
        textinfo = "percent",
        customdata = df_top["formatted_value"].to_numpy().reshape(-1, 1),
        hovertemplate = "<b>%{label}</b><br>"
                        f"{label_name}: "
                        "%{customdata[0]}<br>"
                        "Percent: %{percent}",
        marker = dict(line = dict(color = "#ffffff", width = 1)),
    )

    fig.update_layout(
        title = pie_title_for_publisher(publisher_name, metric),
        title_x = 0.5,
        margin = dict(l = 10, r = 10, t = 40, b = 60),
        height = 360,
        legend = dict(
            orientation = "h",
            yanchor = "top",
            y = -0.05,
            xanchor = "center",
            x = 0.5,
            font = dict(size = 11),
            itemsizing = "trace",
        ),
    )
    return fig

# ---------- layout ----------

def layout():
    return html.Div(
        [
            # dcc.Store(id="publisher-selected"),
            # 🔹 存 Top / Worst 模式
            dcc.Store(
                id = "publisher-mode"
            ),
            html.Div(
                [
                    html.H2("Publishers Overview", className="section-title"),
                    html.Div(
                        [
                            html.Div(className="publisher-slider"),
                            html.Button(
                                "Top 5",
                                id="publisher-top-btn",
                                n_clicks=0,
                                className="publisher-pill-tab publisher-pill-left",
                            ),
                            html.Button(
                                "Worst 5",
                                id="publisher-worst-btn",
                                n_clicks=0,
                                className="publisher-pill-tab publisher-pill-right",
                            ),
                        ],
                        id="publisher-toggle-pill",
                        className="publisher-pill top-active",
                    ),
                ],
                className="section-header",
            ),
            html.Div(
                [
                    html.Div(
                        dcc.Graph(
                            id="publisher-overview-graph",
                            style={"height": "360px"},
                            config={"doubleClick": False, "displayModeBar": True},
                        ),
                        style={"flex": 3, "marginRight": "24px", "pointerEvents": "none"},
                    ),
                    html.Div(
                        dcc.Loading(
                            dcc.Graph(
                                id="publisher-games-pie",
                                style={"height": "360px"},
                            ),
                            type = "circle",
                        ),
                        style={"flex": 1.2, "minWidth": "260px"}, 
                    ),
                ],
                style={"display": "flex", "alignItems": "stretch"},
            ),
        ]
    )


# ---------- callback ----------

@callback(
    Output("publisher-overview-graph", "figure"),
    Output("publisher-games-pie", "figure"),
    # Output("publisher-selected", "data"),
    Output("publisher-toggle-pill", "className"),
    Output("publisher-mode", "data"),
    Input("publisher-worst-btn", "n_clicks"),
    Input("publisher-top-btn", "n_clicks"),
    # Input("publisher-clear-btn", "n_clicks"),
    Input("publisher-overview-graph", "clickData"),
    # Input("publisher-overview-graph", "selectedData"),
    Input("metric-toggle", "value"), # "revenue" or "units"
    Input("global-start-ym", "value"),
    Input("global-end-ym", "value"),

    State("publisher-mode", "data"),
    # State("publisher-selected", "data"), # 目前已選的 publisher
)
def update_publisher_overview(
    n_worst,
    n_top,
    # n_clear,
    click_data,
    # selected_data,
    metric,
    start_ym,
    end_ym,
    current_mode,
    # selected_publisher
):
    """
    Main callback for the Publisher Overview section.

    Logic:
    1. Normalize the date range (fill defaults, fix reversed range).
    2. Decide whether to show Top 5 or Worst 5 publishers based on button clicks.
    3. Build / update the treemap whenever:
        - initial load, or
        - Worst 5 / Top 5 button is clicked.
    4. Handle the pie chart:
        - If there is no publisher data, show an empty placeholder.
        - If "Clear selection" is clicked, reset the pie chart to placeholder.
        - Otherwise, read hoverData from the treemap and show that publisher's games.
    """

    # 處理年月範圍
    start_ym, end_ym = _normalize_month_range(start_ym, end_ym)

    trigger_id = ctx.triggered_id # 預設是 metric-toggle

    # 1. Top / Worst 模式
    mode_label = current_mode or "Top"
    if ctx.triggered_id == "publisher-top-btn":
        mode_label = "Top"
    elif ctx.triggered_id == "publisher-worst-btn":
        mode_label = "Worst"

    pill_class = (
        "publisher-pill top-active"
        if mode_label == "Top"
        else "publisher-pill worst-active"
    )

    df_pub = _publisher_df(start_ym = start_ym, end_ym = end_ym)
    treemap_fig = _publisher_treemap(df_pub, mode_label, metric)
    # Pie chart 預設為空白
    pie_fig = _empty_pie_placeholder("Select a publisher from treemap")

    # 沒資料就直接回空圖
    if df_pub.empty:
        pie_fig = _empty_pie_placeholder("No publisher data")
        return treemap_fig, pie_fig, pill_class, mode_label

    # Top/Worst：不保留選取，不畫 pie
    if trigger_id in ("publisher-top-btn", "publisher-worst-btn"):
        # selected_publisher = None
        return treemap_fig, pie_fig, pill_class, mode_label

    # ---------- 先算目前 treemap 是否選到 publisher ----------
    selected_publisher = None

    if click_data and "points" in click_data and click_data["points"]:
        point = click_data["points"][0]
        if point.get("entry") == "":
            selected_publisher = point["customdata"][0]

    # ===== 🔹 新增的判斷：日期 / metric 變動 =====
    if trigger_id in ("metric-toggle", "global-start-ym", "global-end-ym"):
        if selected_publisher:
            pie_fig = _publisher_games_pie(
                selected_publisher,
                start_ym = start_ym,
                end_ym = end_ym,
                metric = metric,
            )
        else:
            pie_fig = _empty_pie_placeholder("Select a publisher from treemap")
        return treemap_fig, pie_fig, pill_class, mode_label
    
    # ---------- 其他情況：看 clickData，更新 pie ----------
    if len(click_data["points"][0]) == 8:
        pie_fig = _empty_pie_placeholder("To refresh the details, <br>move the cursor away <br>and select the publisher again.")
        return treemap_fig, pie_fig, pill_class, mode_label
    
    if trigger_id == "publisher-overview-graph" and click_data:
        point = click_data["points"][0]

        publisher_name = point["customdata"][0]
        entry = point.get("entry")
        # publisher_name = click_data["points"][0]["customdata"][0]

        if "entry" in click_data["points"][0]:
            entry = click_data["points"][0]["entry"]
            if entry == '':
                pie_fig = _publisher_games_pie(publisher_name, start_ym = start_ym, end_ym = end_ym, 
                                               metric = metric,)
            else:
                pie_fig = _empty_pie_placeholder("Select a publisher from treemap")
        else:
            pie_fig = _empty_pie_placeholder("Select a publisher from treemap")
    
    return treemap_fig, pie_fig, pill_class, mode_label

def pie_title_for_publisher(publisher_name: str, metric: str) -> str:
    """
    Render donut title with truncated publisher name if necessary.
    """
    max_len = 28
    display_name = (
        publisher_name if len(publisher_name) <= max_len else f"{publisher_name[:max_len]}…"
    )
    title_metric = "Revenue Share" if metric == "revenue" else "Units Sold"
    return f"Game {title_metric}<br><sup>{display_name}</sup>"
