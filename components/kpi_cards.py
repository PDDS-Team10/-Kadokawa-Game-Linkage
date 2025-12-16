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
from utils.query import read_df
from datetime import datetime
from dash_iconify import DashIconify
from dash import html, Input, Output, callback, dcc
from dateutil.relativedelta import relativedelta

def _fetch_latest_month():
    sql = """
        SELECT 
            MAX(year_month) AS latest_ym
        FROM SaleMonthly;
    """
    df = read_df(sql)
    if df.empty or df.iloc[0]["latest_ym"] is None:
        return None
    return df.iloc[0]["latest_ym"]

def _fetch_monthly_totals(target_ym):
    sql = """
        SELECT
            SUM(revenue_jpy) AS total_revenue_jpy,
            SUM(sales_units) AS total_units
        FROM SaleMonthly
        WHERE year_month = ?;
    """
    df = read_df(sql, [target_ym])
    if df.empty:
        return {"revenue": 0, "units": 0}
    row = df.iloc[0]
    return {
        "revenue": row.get("total_revenue_jpy", 0) or 0,
        "units": row.get("total_units", 0) or 0,
    }

def _prev_month(ym):
    d = datetime.strptime(ym, "%Y-%m")
    return (d - relativedelta(months = 1)).strftime("%Y-%m")

def _yoy_month(ym):
    d = datetime.strptime(ym, "%Y-%m")
    return (d - relativedelta(years = 1)).strftime("%Y-%m")

def _fetch_total_kpis():
    latest_ym = _fetch_latest_month()
    if latest_ym is None:
        return None

    prev_one_month_ym = _prev_month(latest_ym)
    prev_year_ym = _yoy_month(latest_ym)

    latest_data = _fetch_monthly_totals(latest_ym)
    prev_one_month_data   = _fetch_monthly_totals(prev_one_month_ym)
    prev_year_data    = _fetch_monthly_totals(prev_year_ym)
    return {
        "latest_ym": latest_ym,
        "prev_one_month_ym": prev_one_month_ym,
        "prev_year_ym": prev_year_ym,
        "latest_data": latest_data,
        "prev_one_month_data": prev_one_month_data,
        "prev_year_data": prev_year_data,
    }

def _fetch_latest_best_publisher():
    sql = """
        SELECT 
            p.publisher_name AS publisher,
            SUM(m.sales_units) AS units
        FROM SaleMonthly m
        JOIN GAME g ON m.game_id = g.game_id
        JOIN PUBLISHER p ON g.publisher_id = p.publisher_id
        WHERE m.year_month = (
            SELECT MAX(year_month) FROM SaleMonthly
        )
        GROUP BY publisher
        ORDER BY units DESC
        LIMIT 1;
    """
    df = read_df(sql)
    if df.empty:
        return None

    row = df.iloc[0]
    return {
        "publisher": row["publisher"],
        "units": row["units"],
    }

def _fetch_publisher_units(publisher, target_ym):
    sql = """
        SELECT 
            SUM(m.sales_units) AS units
        FROM SaleMonthly m
        JOIN GAME g ON m.game_id = g.game_id
        JOIN PUBLISHER p ON g.publisher_id = p.publisher_id
        WHERE p.publisher_name = ?
          AND m.year_month = ?;
    """
    df = read_df(sql, [publisher, target_ym])
    if df.empty:
        return 0
    return df.iloc[0]["units"] or 0

def _fetch_best_publisher_kpis():
    # Step 1. 找最新月份
    latest_sql = "SELECT MAX(year_month) AS latest_ym FROM SaleMonthly;"
    latest_df = read_df(latest_sql)
    latest_ym = latest_df.iloc[0]["latest_ym"]

    # Step 2. 找最新月份的勝出 publisher
    winner = _fetch_latest_best_publisher()
    if winner is None:
        return None
    
    publisher = winner["publisher"]

    # Step 3. 計算相鄰月份
    prev_one_month_ym = _prev_month(latest_ym)
    prev_year_ym  = _yoy_month(latest_ym)

    # Step 4. 查詢這家 publisher 在三個月份的 units
    curr_units = winner["units"]  # 最新月份已取得
    prev_one_month_units = _fetch_publisher_units(publisher, prev_one_month_ym)
    prev_year_units  = _fetch_publisher_units(publisher, prev_year_ym)

    return {
        "publisher": publisher,
        "latest_ym": latest_ym,
        "prev_one_month_ym": prev_one_month_ym,
        "prev_year_ym": prev_year_ym,
        "units": {
            "latest": curr_units,
            "prev_one_month": prev_one_month_units,
            "prev_year": prev_year_units,
        }
    }

def _format_number(n):
    try:
        return f"{int(n):,}"
    except (TypeError, ValueError):
        return "0"

def _calc_growth(current, previous):
    if current is None or previous in (None, 0):
        return None
    try:
        return current / previous - 1
    except ZeroDivisionError:
        return None

def _render_delta_line(label, value):
    text = "No data" if value is None else f"{value:+.2%} {label}"
    tone = "positive" if value and value > 0 else "negative" if value and value < 0 else "neutral"
    return html.Div(text, className = f"kpi-delta {tone}")

def _build_kpi_card(title, value, subtitle, icon, yoy_delta, mom_delta):
    return html.Div(
        className = "kpi-card",
        children = [
            html.Div(
                className = "kpi-card-left",
                children = [
                    html.Div(title, className = "kpi-card-title"),
                    html.Div(value, className = "kpi-card-value"),
                    html.Div(subtitle, className = "kpi-card-subtitle") if subtitle else None,
                ],
            ),
            html.Div(
                className = "kpi-card-right",
                children = [
                    html.Div(
                        DashIconify(icon = icon, width = 22, height = 22, color = "#ffffff"),
                        className = "kpi-icon-badge",
                    ),
                    html.Div(
                        [_render_delta_line("YoY", yoy_delta), _render_delta_line("MoM", mom_delta)],
                        className = "kpi-delta-group",
                    ),
                ],
            ),
        ],
    )

def layout():
    """
    這個 component 只負責放一個容器，真正的卡片內容由 callback 填進來
    """
    return html.Div(
        id = "kpi-panel-container",
        className = "kpi-panel-wrapper",
    )

# def _fetch_total_df(start_ym, end_ym):
#     sql = """
#     SELECT
#         SUM(m.revenue_jpy)        AS total_revenue_jpy,
#         SUM(m.sales_units)         AS total_units
#     FROM SaleMonthly m
#     WHERE m.year_month BETWEEN ? AND ?;
#     """
#     return read_df(sql, [start_ym, end_ym])


# def _fetch_best_publisher_df(start_ym, end_ym):
#     sql = """
#     SELECT 
#         p.publisher_name AS publisher,
#         SUM(m.sales_units) AS units
#     FROM SaleMonthly m
#     JOIN GAME g
#         on m.game_id = g.game_id
#     JOIN PUBLISHER p
#         on g.publisher_id = p.publisher_id
#     WHERE m.year_month BETWEEN ? AND ?
#     GROUP BY publisher
#     ORDER BY units DESC
#     LIMIT 1;
#     """
#     return read_df(sql, [start_ym, end_ym])

@callback(
    Output("kpi-panel-container", "children"),
    Input("url", "pathname"), # 頁面載入時會觸發一次
    # Input("global-start-ym", "value"),
    # Input("global-end-ym", "value"),
)
def update_kpis(root):
    kpi = _fetch_total_kpis()

    if not kpi:
        return html.Div("No KPI data", className = "kpi-panel")

    curr_revenue = kpi["latest_data"]["revenue"]
    curr_units   = kpi["latest_data"]["units"]

    curr_revenue_text = f"{_format_number(curr_revenue)} JPY"
    curr_units_text = _format_number(curr_units)

    prev_one_month_revenue = kpi["prev_one_month_data"]["revenue"]
    prev_one_month_units   = kpi["prev_one_month_data"]["units"]
    prev_year_revenue  = kpi["prev_year_data"]["revenue"]
    prev_year_units    = kpi["prev_year_data"]["units"]

    mom_revenue_pct = _calc_growth(curr_revenue, prev_one_month_revenue)
    yoy_revenue_pct = _calc_growth(curr_revenue, prev_year_revenue)
    mom_units_pct   = _calc_growth(curr_units, prev_one_month_units)
    yoy_units_pct   = _calc_growth(curr_units, prev_year_units)

    pub_kpi = _fetch_best_publisher_kpis()

    best_publisher = pub_kpi["publisher"] if pub_kpi else "-"
    best_pub_curr_units = pub_kpi["units"]["latest"] if pub_kpi else None
    best_pub_curr_units_text = _format_number(best_pub_curr_units) if best_pub_curr_units is not None else "-"

    prev_one_month_pub_units = pub_kpi["units"].get("prev_one_month") if pub_kpi else None
    prev_year_pub_units      = pub_kpi["units"].get("prev_year") if pub_kpi else None

    mom_pub_units_pct = _calc_growth(best_pub_curr_units, prev_one_month_pub_units)
    yoy_pub_units_pct = _calc_growth(best_pub_curr_units, prev_year_pub_units)

    # # 防呆：第一次載入還沒選值時，先給預設區間
    # if not start_ym:
    #     start_ym = "2022-01"
    # if not end_ym:
    #     end_ym = "2024-12"

    # # ① 原本 KPI：總營收、總銷量、標題數
    # total_df = _fetch_total_df(start_ym, end_ym)

    # if total_df.empty:
    #     total_revenue = 0
    #     total_units = 0
    #     # num_titles = 0
    # else:
    #     row = total_df.iloc[0]
    #     total_revenue = row.get("total_revenue_jpy", 0) or 0
    #     total_units = row.get("total_units", 0) or 0
    #     # num_titles = row.get("num_titles", 0) or 0

    # # 轉成好看的文字
    # total_revenue_text = f"{_format_number(total_revenue)} JPY"
    # total_units_text = _format_number(total_units)
    # # num_titles_text = _format_number(num_titles)

    # # ② 新 KPI：這段期間賣最好的 publisher + units
    # best_df = _fetch_best_publisher_df(start_ym, end_ym)
    # if best_df.empty:
    #     best_publisher = "-"
    #     best_units = 0
    # else:
    #     best_row = best_df.iloc[0]
    #     best_publisher = best_row.get("publisher", "-") or "-"
    #     best_units = best_row.get("units", 0) or 0

    # best_units_text = f"{_format_number(best_units)} Units Sold"

    # ③ 卡片 layout：前兩張維持原本，第三張換成 Best-selling Publisher
    cards = [
        _build_kpi_card(
            title = "Total Revenue",
            value = curr_revenue_text,
            subtitle = None,
            icon = "bi:currency-dollar",
            yoy_delta = yoy_revenue_pct,
            mom_delta = mom_revenue_pct,
        ),
        _build_kpi_card(
            title = "Total Units Sold",
            value = curr_units_text,
            subtitle = None,
            icon = "bi:bag",
            yoy_delta = yoy_units_pct,
            mom_delta = mom_units_pct,
        ),
        _build_kpi_card(
            title = "Best-selling Publisher",
            value = best_pub_curr_units_text,
            subtitle = best_publisher,
            icon = "bi:award",
            yoy_delta = yoy_pub_units_pct,
            mom_delta = mom_pub_units_pct,
        ),
    ]

    return html.Div(
        className = "kpi-panel",
        children = html.Div(cards, className = "kpi-grid"),
    )
