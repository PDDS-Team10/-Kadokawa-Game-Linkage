# components/kpi_cards.py
#
# This component is responsible for showing 3 KPI cards on the top of the dashboard:
#   - Total Revenue (JPY)
#   - Total Units Sold
#   - Number of Titles
#
# How it works (for teammates):
# - layout() only returns an empty container <div>. It does NOT render the cards itself.
# - The Dash callback `update_kpis` listens to the global date range inputs
#   (`global-start-ym`, `global-end-ym`) and fills this container with 3 cards.
# - If you want to add a new KPI card, you only need to:
#     1. Update the SQL in `_fetch_kpi_df` to compute the new metric.
#     2. Add one more `dbc.Col(...)` block in `update_kpis`'s `cards` layout.
from dash import html, Input, Output, callback
import dash_bootstrap_components as dbc
from utils.query import read_df


def _fetch_kpi_df(start_ym, end_ym):
    sql = """
    SELECT
        SUM(m.revenue_jpy)        AS total_revenue_jpy,
        SUM(m.sales_units)         AS total_units,
        COUNT(DISTINCT m.game_id) AS num_titles
    FROM SaleMonthly m
    WHERE m.year_month BETWEEN ? AND ?;
    """
    return read_df(sql, [start_ym, end_ym])


def _format_number(n):
    try:
        return f"{int(n):,}"
    except (TypeError, ValueError):
        return "0"


def layout():
    """
    這個 component 只負責放一個容器，真正的卡片內容由 callback 填進來
    """
    return html.Div(
        id="kpi-cards-row",
        style={"marginBottom": "24px"},
    )


@callback(
    Output("kpi-cards-row", "children"),
    Input("global-start-ym", "value"),
    Input("global-end-ym", "value"),
)
def update_kpis(start_ym, end_ym):
    # 防呆：第一次載入還沒選值時，先給預設區間
    if not start_ym:
        start_ym = "2022-01"
    if not end_ym:
        end_ym = "2024-12"

    df = _fetch_kpi_df(start_ym, end_ym)

    if df.empty:
        total_revenue = 0
        total_units = 0
        num_titles = 0
    else:
        row = df.iloc[0]
        total_revenue = row.get("total_revenue_jpy", 0) or 0
        total_units = row.get("total_units", 0) or 0
        num_titles = row.get("num_titles", 0) or 0

    # 轉成好看的文字
    total_revenue_text = f"{_format_number(total_revenue)} JPY"
    total_units_text = _format_number(total_units)
    num_titles_text = _format_number(num_titles)

    cards = dbc.Row(
        [
            dbc.Col(
                dbc.Card(
                    [
                        dbc.CardHeader("Total Revenue"),
                        dbc.CardBody(
                            html.H4(total_revenue_text, className="card-title")
                        ),
                    ],
                    className="h-100",
                ),
                md=4,
            ),
            dbc.Col(
                dbc.Card(
                    [
                        dbc.CardHeader("Total Units Sold"),
                        dbc.CardBody(
                            html.H4(total_units_text, className="card-title")
                        ),
                    ],
                    className="h-100",
                ),
                md=4,
            ),
            dbc.Col(
                dbc.Card(
                    [
                        dbc.CardHeader("Number of Titles"),
                        dbc.CardBody(
                            html.H4(num_titles_text, className="card-title")
                        ),
                    ],
                    className="h-100",
                ),
                md=4,
            ),
        ],
        className="gy-3",  # row 之間一點垂直間距
    )

    return cards
