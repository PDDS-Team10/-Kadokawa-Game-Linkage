# components/publisher_overview.py
#
# Publisher Overview section
#
# This component shows:
#   - A treemap of publishers (Top 5 / Worst 5 by revenue).
#   - A pie chart of game revenue share for the hovered publisher.
#
# Interaction:
#   - "Worst 5" / "Top 5" buttons switch the treemap mode.
#   - Hovering on a publisher block in the treemap updates the pie chart on the right.
#   - "Clear selection" resets the pie chart to a placeholder state.
#   - Global date range (`global-start-ym`, `global-end-ym`) affects both charts.
#
# For teammates:
# - To change the visual style (height, colors, text), you can edit `layout()` and
#   the figure builders `_publisher_treemap` / `_publisher_games_pie`.
# - To change the logic of "Top/Worst 5", adjust `_publisher_df` and the part in
#   `update_publisher_overview` that decides `order` and `mode_label`.

from dash import html, dcc, Input, Output, callback, ctx, no_update
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


def _publisher_df(order="ASC", limit=5, start_ym="2022-01", end_ym="2024-12"):
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
    df["area_value"] = (df["revenue"].clip(lower=0) ** 0.5)

    fig = px.treemap(
        df,
        path=["publisher_name"],
        values="area_value",
        color="revenue",
        color_continuous_scale="Blues",
        title=f"{mode_label} 5 Publishers by Revenue",
    )

    # Custom hover text to show nicely formatted revenue
    fig.update_traces(
        customdata=df[["revenue"]].to_numpy(),
        hovertemplate="<b>%{label}</b><br>"
                      "Revenue: %{customdata[0]:,.0f} JPY<extra></extra>",
    )

    fig.update_layout(
        margin=dict(l=10, r=10, t=40, b=10),
        height=380,
    )
    return fig


def _games_df_for_publisher(publisher_name, start_ym="2022-01", end_ym="2024-12", limit=8):
    sql = """
    SELECT 
        g.game_name,
        SUM(m.revenue_jpy) AS revenue
    FROM SaleMonthly m
    JOIN GAME g      ON m.game_id = g.game_id
    JOIN PUBLISHER p ON g.publisher_id = p.publisher_id
    WHERE p.publisher_name = ?
      AND m.year_month BETWEEN ? AND ?
    GROUP BY g.game_name
    ORDER BY revenue DESC
    LIMIT ?;
    """
    return read_df(sql, [publisher_name, start_ym, end_ym, limit])


def _publisher_games_pie(publisher_name, start_ym, end_ym):
    """
    Build the pie chart for one publisher's game revenue share.
    """
    df = _games_df_for_publisher(publisher_name, start_ym=start_ym, end_ym=end_ym)
    if df.empty:
        return _empty_pie_placeholder(f"{publisher_name}: no game data")

    fig = px.pie(
        df,
        names="game_name",
        values="revenue",
        title=f"Games Revenue Share – {publisher_name}",
    )
    fig.update_layout(
        margin=dict(l=10, r=10, t=40, b=10),
        height=380,
    )
    return fig


def _empty_pie_placeholder(message="Select a publisher from treemap"):
    """
    Build a placeholder pie chart when there is no selection or no data.
    """
    fig = px.pie(
        names=["No selection"],
        values=[1],
        title=message,
    )
    fig.update_layout(
        showlegend=False,
        margin=dict(l=10, r=10, t=40, b=10),
        height=380,
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
            html.H3("Publisher Overview", style={"marginBottom": "8px"}),

            html.Div(
                [
                    html.Button(
                        "Worst 5",
                        id="publisher-worst-btn",
                        n_clicks=0,
                        style={
                            "marginRight": "10px",
                            "padding": "6px 16px",
                            "borderRadius": "6px",
                            "background": "#d9534f",
                            "color": "white",
                            "border": "none",
                        },
                    ),
                    html.Button(
                        "Top 5",
                        id="publisher-top-btn",
                        n_clicks=0,
                        style={
                            "marginRight": "10px",
                            "padding": "6px 16px",
                            "borderRadius": "6px",
                            "background": "#5cb85c",
                            "color": "white",
                            "border": "none",
                        },
                    ),
                    html.Button(
                        "Clear selection",
                        id="publisher-clear-btn",
                        n_clicks=0,
                        style={
                            "padding": "6px 16px",
                            "borderRadius": "6px",
                            "background": "#f0f0f0",
                            "color": "#333",
                            "border": "1px solid #ccc",
                        },
                    ),
                ],
                style={"marginBottom": "16px"},
            ),
            # Main content: treemap (left) + games pie (right)
            html.Div(
                [
                    html.Div(
                        [
                            dcc.Graph(
                                id="publisher-overview-graph",
                                style={"height": "380px"},
                                config={
                                    "doubleClick": False,
                                    "displayModeBar": True,
                                },
                            ),
                        ],
                        style={"flex": "3", "marginRight": "16px"},
                    ),
                    html.Div(
                        [
                            dcc.Graph(
                                id="publisher-games-pie",
                                style={"height": "380px"},
                            ),
                        ],
                        style={"flex": "2"},
                    ),
                ],
                style={"display": "flex", "flexDirection": "row"},
            ),
        ],
        style={"marginBottom": "24px"},
    )


# ---------- callback ----------

@callback(
    Output("publisher-overview-graph", "figure"),
    Output("publisher-games-pie", "figure"),
    Input("publisher-worst-btn", "n_clicks"),
    Input("publisher-top-btn", "n_clicks"),
    Input("publisher-clear-btn", "n_clicks"),
    Input("publisher-overview-graph", "hoverData"),
    Input("global-start-ym", "value"),
    Input("global-end-ym", "value"),
)
def update_publisher_overview(
    n_worst,
    n_top,
    n_clear,
    hover_data,
    start_ym,
    end_ym,
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

    # 1. Top / Worst 模式
    if n_top > n_worst:
        order = "DESC"
        mode_label = "Top"
    else:
        order = "ASC"
        mode_label = "Worst"

    df_pub = _publisher_df(order=order, limit=5, start_ym=start_ym, end_ym=end_ym)

    trigger_id = ctx.triggered_id

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
        return treemap_fig, pie_fig

    # Clear 按鈕：只清右邊 pie
    if trigger_id == "publisher-clear-btn":
        pie_fig = _empty_pie_placeholder("Select a publisher from treemap")
        return treemap_fig, pie_fig

    # 其他情況：看 hoverData
    publisher_name = None
    if hover_data and "points" in hover_data and hover_data["points"]:
        publisher_name = hover_data["points"][0].get("label")

    if publisher_name and publisher_name in set(df_pub["publisher_name"]):
        pie_fig = _publisher_games_pie(
            publisher_name,
            start_ym=start_ym,
            end_ym=end_ym,
        )
    else:
        pie_fig = _empty_pie_placeholder("Select a publisher from treemap")

    return treemap_fig, pie_fig
