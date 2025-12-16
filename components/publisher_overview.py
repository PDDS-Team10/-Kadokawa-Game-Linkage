# components/publisher_overview.py
#
# Publisher Overview section
#
# This component shows:
#   - A treemap of publishers (Top 5 / Worst 5 by revenue).
#   - A pie chart of game revenue share for the hovered publisher.
#
# Interaction:
#   - "Top 5" / "Worst 5" buttons switch the treemap mode.
#   - Hovering on a publisher block in the treemap updates the pie chart on the right.
#   - Global date range (`global-start-ym`, `global-end-ym`) affects both charts.
#
# For teammates:
# - To change the visual style (height, colors, text), you can edit `layout()` and
#   the figure builders `_publisher_treemap` / `_publisher_games_pie`.
# - To change the logic of "Top/Worst 5", adjust `_publisher_df` and the part in
#   `update_publisher_overview` that decides `order` and `mode_label`.

import pandas as pd
from dash import html, dcc, Input, Output, callback, ctx, no_update, State
import plotly.express as px
from utils.query import read_df

# ---------- helpers ----------

def _normalize_month_range(start_ym, end_ym):
    if not start_ym:
        start_ym = "2022-01"
    if not end_ym:
        end_ym = "2024-12"
    if start_ym > end_ym:
        start_ym, end_ym = end_ym, start_ym
    return start_ym, end_ym


def _publisher_df(order = "ASC", limit = 5, start_ym = "2022-01", end_ym = "2024-12"):
    sql = f"""
    SELECT 
        p.publisher_name,
        SUM(m.revenue_jpy) AS revenue
    FROM SaleMonthly m
    JOIN GAME g      ON m.game_id = g.game_id
    JOIN PUBLISHER p ON g.publisher_id = p.publisher_id
    WHERE m.year_month BETWEEN ? AND ?
    GROUP BY p.publisher_name
    ORDER BY revenue {order}
    LIMIT ?;
    """
    return read_df(sql, [start_ym, end_ym, limit])


def _publisher_treemap(df, mode_label):
    """
    Build the treemap for publishers.

    - The rectangle size is based on sqrt(revenue) to reduce extreme skew.
    - Color is still mapped to raw revenue.
    """
    df = df.copy()
    df["area_value"] = (df["revenue"].clip(lower = 0) ** 0.5)

    # 排序確保 Top/Worst 左上位置正確
    if mode_label == "Top":
        df = df.sort_values("revenue", ascending = False)
    else:  # Worst
        df = df.sort_values("revenue", ascending = True)

    fig = px.treemap(
        df,
        path = ["publisher_name"],
        values = "area_value",
        color = "revenue",
        color_continuous_scale = "Blues",
        title = f"{mode_label} 5 Publishers by Revenue",
    )

    # Custom hover text to show nicely formatted revenue
    fig.update_traces(
        customdata = df[["publisher_name", "revenue"]].to_numpy(),
        hovertemplate = "<b>%{label}</b><br>"
                      "Revenue: %{customdata[1]:,.0f} JPY<extra></extra>",
    )

    fig.update_layout(
        margin = dict(l = 0, r = 10, t = 40, b = 10),
        height = 380,
        title_x = 0
    )
    return fig


def _games_df_for_publisher(publisher_name, start_ym = "2022-01", end_ym = "2024-12"):
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

    fig = px.pie(
        df_top,
        names = "game_name",
        values = metric,
        title = f"Games { 'Revenue' if metric == 'revenue' else 'Units Sold' } Share – {publisher_name}"
    )
    fig.update_layout(
        margin = dict(l = 10, r = 10, t = 40, b = 10),
        height = 380,
    )
    return fig

# ---------- layout ----------

def layout():
    """
    Layout for the Publisher Overview section.

    Contains:
    - H3 title.
    - Three buttons (Worst 5 / Top 5 / Clear selection).
    - A flex row:
        - Left: treemap (publisher overview).
        - Right: pie chart (game share for selected publisher).

    In comment:
    - 按鈕樣式可以直接改 style 裡的顏色、padding、邊框
    """
    return html.Div(
        [
            dcc.Store(id = "publisher-selected"),
            html.H3("Publishers Overview", style = {"marginBottom": "8px"}),

            html.Div(
                [
                    html.Button(
                        "Top 5",
                        id = "publisher-top-btn",
                        n_clicks = 0,
                        style = {
                            "marginRight": "10px",
                            "padding": "6px 16px",
                            "borderRadius": "6px",
                            "background": "#5cb85c",
                            "color": "white",
                            "border": "none",
                            "minWidth": "90px"
                        },
                    ),
                    html.Button(
                        "Worst 5",
                        id = "publisher-worst-btn",
                        n_clicks = 0,
                        style = {
                            "marginRight": "10px",
                            "padding": "6px 16px",
                            "borderRadius": "6px",
                            "background": "#d9534f",
                            "color": "white",
                            "border": "none",
                            "minWidth": "60px"
                        },
                    ),
                    # html.Button(
                    #     "Clear selection",
                    #     id = "publisher-clear-btn",
                    #     n_clicks = 0,
                    #     style = {
                    #         "padding": "6px 16px",
                    #         "borderRadius": "6px",
                    #         "background": "#f0f0f0",
                    #         "color": "#333",
                    #         "border": "1px solid #ccc",
                    #     },
                    # ),
                ],
                style = {"marginBottom": "16px"},
            ),
            # Main content: treemap (left) + games pie (right)
            html.Div(
                [
                    html.Div(
                        [
                            dcc.Graph(
                                id = "publisher-overview-graph",
                                style = {"height": "380px"},
                                config = {
                                    "doubleClick": False,
                                    "displayModeBar": True,
                                },
                            ),
                        ],
                        style = {"flex": "3", "marginRight": "16px"},
                    ),
                    html.Div(
                        [
                            dcc.Graph(
                                id = "publisher-games-pie",
                                style = {"height": "380px"},
                            ),
                        ],
                        style = {"flex": "2"},
                    ),
                ],
                style = {"display": "flex", "flexDirection": "row"},
            ),
        ],
        style = {"marginBottom": "24px"},
    )


# ---------- callback ----------

@callback(
    Output("publisher-overview-graph", "figure"),
    Output("publisher-games-pie", "figure"),
    Output("publisher-selected", "data"), 
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

    df_pub = _publisher_df(order = order, limit = 5, start_ym = start_ym, end_ym = end_ym)
    treemap_fig = _publisher_treemap(df_pub, mode_label)

    # 如果是切換 metric：treemap 重新畫（回到 Top/Worst 初始狀態）
    if trigger_id == "metric-toggle":
        treemap_fig = _publisher_treemap(df_pub, mode_label)
        return treemap_fig, _empty_pie_placeholder("Select a publisher from treemap"), None

    # --- 如果是切換 Top/Worst：直接回傳空 pie ---
    if trigger_id in ("publisher-top-btn", "publisher-worst-btn"):
        return treemap_fig, _empty_pie_placeholder("Select a publisher from treemap"), None

    # Treemap：初始載入 / Top/Worst 切換 / 日期改變，都要重畫
    if trigger_id in (
        None,
        "publisher-worst-btn",
        "publisher-top-btn",
        "global-start-ym",
        "global-end-ym",
    ):
        treemap_fig = _publisher_treemap(df_pub, mode_label)
    else:
        treemap_fig = no_update

    # 沒資料就直接回空圖
    if df_pub.empty:
        if treemap_fig is no_update:
            treemap_fig = _publisher_treemap(df_pub, mode_label)
        pie_fig = _empty_pie_placeholder("No publisher data")
        return treemap_fig, pie_fig, None

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

    return treemap_fig, pie_fig, selected_publisher
