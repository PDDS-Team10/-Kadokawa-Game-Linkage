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
        paper_bgcolor = "rgba(0,0,0,0)",
        plot_bgcolor = "rgba(0,0,0,0)",
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
    fig = px.pie(
        names = ["No selection"],
        values = [1],
        title = message,
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
        return _empty_pie_placeholder(f"{publisher_name}: no game data")
    
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
    )

    label_name = "Revenue" if metric == "revenue" else "Units Sold"

    fig.update_traces(
        textinfo = "percent",
        customdata = df_top["formatted_value"].to_numpy().reshape(-1, 1),
        hovertemplate = "<b>%{label}</b><br>" +
                        f"{label_name}: " + 
                        "%{customdata[0]}<br>" + 
                        "Percent: %{percent}"
    )

    fig.update_layout(
        title = pie_title_for_publisher(publisher_name),
        title_x = 0.5,
        margin = dict(l = 40, r = 40, t = 80, b = 40),
        height = 380,
    )
    return fig

# ---------- layout ----------

def layout():
    return html.Div(
        [
            dcc.Store(id="publisher-selected"),
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
                        style={"flex": 2.2, "marginRight": "24px"},
                    ),
                    html.Div(
                        dcc.Graph(
                            id="publisher-games-pie",
                            style={"height": "360px"},
                        ),
                        style={"flex": 1, "minWidth": "260px"},
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
    Output("publisher-selected", "data"),
    Output("publisher-toggle-pill", "className"),
    Input("publisher-worst-btn", "n_clicks"),
    Input("publisher-top-btn", "n_clicks"),
    # Input("publisher-clear-btn", "n_clicks"),
    Input("publisher-overview-graph", "clickData"),
    Input("metric-toggle", "value"), # "revenue" or "units"
    Input("global-start-ym", "value"),
    Input("global-end-ym", "value"),

    State("publisher-selected", "data"), # 目前已選的 publisher
)
def update_publisher_overview(
    n_worst,
    n_top,
    # n_clear,
    click_data,
    metric,
    start_ym,
    end_ym,
    selected_publisher
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

    trigger_id = ctx.triggered_id

    # 1. Top / Worst 模式
    # --- 依照按鈕直接決定模式，不看 n_clicks 大小 ---
    if trigger_id == "publisher-top-btn":
        order = "DESC"
        mode_label = "Top"
    elif trigger_id == "publisher-worst-btn":
        order = "ASC"
        mode_label = "Worst"
    else:
        order = "DESC"      # 預設是 Top
        mode_label = "Top"

    pill_class = (
        "publisher-pill top-active"
        if mode_label == "Top"
        else "publisher-pill worst-active"
    )

    df_pub = _publisher_df(start_ym = start_ym, end_ym = end_ym) # order = order, limit = 5, 
    treemap_fig = _publisher_treemap(df_pub, mode_label, metric)
    # Pie chart 預設為空白
    pie_fig = _empty_pie_placeholder("Select a publisher from treemap")

    # Metric toggle or Top/Worst 都：不保留選取，不畫 pie
    if trigger_id in ("metric-toggle", "publisher-top-btn", "publisher-worst-btn"):
        selected_publisher = None
        return treemap_fig, pie_fig, selected_publisher, pill_class

    # # 如果是切換 metric：treemap 重新畫（回到 Top/Worst 初始狀態）
    # if trigger_id == "metric-toggle":
    #     return treemap_fig, _empty_pie_placeholder("Select a publisher from treemap"), None

    # # --- 如果是切換 Top/Worst：直接回傳空 pie ---
    # if trigger_id in ("publisher-top-btn", "publisher-worst-btn"):
    #     return treemap_fig, _empty_pie_placeholder("Select a publisher from treemap"), None

    # Treemap：初始載入 / Top/Worst 切換 / 日期改變，都要重畫
    if trigger_id in (
        None,
        "publisher-worst-btn",
        "publisher-top-btn",
        "global-start-ym",
        "global-end-ym",
    ):
        treemap_fig = _publisher_treemap(df_pub, mode_label, metric)
    else:
        treemap_fig = no_update

    # 沒資料就直接回空圖
    if df_pub.empty:
        if treemap_fig is no_update:
            treemap_fig = _publisher_treemap(df_pub, mode_label, metric)
        pie_fig = _empty_pie_placeholder("No publisher data")
        return treemap_fig, pie_fig, None, pill_class

    # Clear 按鈕：只清右邊 pie
    # if trigger_id == "publisher-clear-btn":
    #     pie_fig = _empty_pie_placeholder("Select a publisher from treemap")
    #     return treemap_fig, pie_fig, None

    # ---------- 其他情況：看 clickData，實作「點第二次取消選取」 ----------
    clicked_name = None
    if click_data and "points" in click_data and click_data["points"]:
        clicked_name = click_data["points"][0]["customdata"][0]

    # 1️⃣ 如果點到同一個 publisher（第二次點），就當作「取消選取」→ 清空 pie
    if clicked_name and clicked_name == selected_publisher:
        pie_fig = _empty_pie_placeholder("Select a publisher from treemap")
        selected_publisher = None

    # 2️⃣ 如果點到新的 publisher，就更新 pie，並記錄這次選取
    elif clicked_name: # and clicked_name in set(df_pub["publisher_name"]):
        pie_fig = _publisher_games_pie(
            clicked_name,
            start_ym = start_ym,
            end_ym = end_ym,
            metric = metric
        )
        selected_publisher = clicked_name

    # 3️⃣ 如果這次沒點到任何 publisher，但之前有選過，就維持上一個選取
    # elif selected_publisher: # and selected_publisher in set(df_pub["publisher_name"]):
    #     pie_fig = _publisher_games_pie(
    #         selected_publisher,
    #         start_ym=start_ym,
    #         end_ym=end_ym,
    #     )

    # 4️⃣ 否則就是完全沒選 → 顯示 placeholder
    else:
        pie_fig = _empty_pie_placeholder("Select a publisher from treemap")
        selected_publisher = None

    return treemap_fig, pie_fig, selected_publisher, pill_class
def pie_title_for_publisher(publisher_name: str) -> str:
    """
    Always render title in two lines to prevent clipping regardless of length.
    """
    return f"Games Revenue Share<br><sup>{publisher_name}</sup>"
