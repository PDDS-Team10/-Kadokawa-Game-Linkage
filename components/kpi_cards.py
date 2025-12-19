# components/kpi_cards.py
#
# This component renders the KPI summary cards that appear at the top of the dashboard.
# It exposes a layout() helper that returns an empty container <div>. The cards are
# injected via the Dash callback update_kpis so that other pages can also reuse this
# component without duplicating SQL logic.

from datetime import datetime

from dash import Input, Output, callback, html
from dash_iconify import DashIconify
from dateutil.relativedelta import relativedelta

from utils.query import read_df


def _fetch_latest_month():
    sql = """
        SELECT MAX(year_month) AS latest_ym
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
    return (d - relativedelta(months=1)).strftime("%Y-%m")


def _yoy_month(ym):
    d = datetime.strptime(ym, "%Y-%m")
    return (d - relativedelta(years=1)).strftime("%Y-%m")


def _fetch_total_kpis():
    latest_ym = _fetch_latest_month()
    if latest_ym is None:
        return None

    prev_one_month_ym = _prev_month(latest_ym)
    prev_year_ym = _yoy_month(latest_ym)

    latest_data = _fetch_monthly_totals(latest_ym)
    prev_one_month_data = _fetch_monthly_totals(prev_one_month_ym)
    prev_year_data = _fetch_monthly_totals(prev_year_ym)
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
        WHERE m.year_month = (SELECT MAX(year_month) FROM SaleMonthly)
        GROUP BY publisher
        ORDER BY units DESC
        LIMIT 1;
    """
    df = read_df(sql)
    if df.empty:
        return None
    row = df.iloc[0]
    return {"publisher": row["publisher"], "units": row["units"]}


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
    latest_sql = "SELECT MAX(year_month) AS latest_ym FROM SaleMonthly;"
    latest_df = read_df(latest_sql)
    latest_ym = latest_df.iloc[0]["latest_ym"]

    winner = _fetch_latest_best_publisher()
    if winner is None:
        return None

    publisher = winner["publisher"]
    prev_one_month_ym = _prev_month(latest_ym)
    prev_year_ym = _yoy_month(latest_ym)

    curr_units = winner["units"]
    prev_one_month_units = _fetch_publisher_units(publisher, prev_one_month_ym)
    prev_year_units = _fetch_publisher_units(publisher, prev_year_ym)

    return {
        "publisher": publisher,
        "latest_ym": latest_ym,
        "prev_one_month_ym": prev_one_month_ym,
        "prev_year_ym": prev_year_ym,
        "units": {
            "latest": curr_units,
            "prev_one_month": prev_one_month_units,
            "prev_year": prev_year_units,
        },
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
    return html.Div(text, className=f"kpi-delta-line {tone}")


def _build_kpi_card(title, value, subtitle, icon, yoy_delta, mom_delta):
    return html.Div(
        className="kpi-card",
        children=[
            html.Div(
                className="kpi-card-left",
                children=[
                    html.Div(
                        className="kpi-card-content",
                        children=[
                            html.Div(title, className="kpi-card-title"),
                            html.Div(
                                [
                                    html.Span(value, className="kpi-card-value"),
                                ],
                                className="kpi-value-group",
                            ),
                            html.Div(subtitle, className="kpi-card-subtext") if subtitle else None,
                        ],
                    ),
                ],
            ),
            html.Div(
                className="kpi-card-right",
                children=[
                    html.Div(
                        DashIconify(icon=icon, width=22, height=22, color="#ffffff"),
                        className="kpi-icon-badge",
                    ),
                    html.Div(
                        [_render_delta_line("MoM", mom_delta), _render_delta_line("YoY", yoy_delta)],
                        className="kpi-delta",
                    ),
                ],
            ),
        ],
    )


def layout():
    return html.Div(id="kpi-panel-container", className="kpi-section")


@callback(
    Output("kpi-panel-container", "children"),
    Input("url", "pathname"),
)
def update_kpis(_):
    kpi = _fetch_total_kpis()
    if not kpi:
        return html.Div("No KPI data", className="kpi-grid-empty")

    curr_revenue = kpi["latest_data"]["revenue"]
    curr_units = kpi["latest_data"]["units"]
    curr_revenue_value = _format_number(curr_revenue)
    curr_units_value = _format_number(curr_units)

    prev_one_month_revenue = kpi["prev_one_month_data"]["revenue"]
    prev_one_month_units = kpi["prev_one_month_data"]["units"]
    prev_year_revenue = kpi["prev_year_data"]["revenue"]
    prev_year_units = kpi["prev_year_data"]["units"]

    mom_revenue_pct = _calc_growth(curr_revenue, prev_one_month_revenue)
    yoy_revenue_pct = _calc_growth(curr_revenue, prev_year_revenue)
    mom_units_pct = _calc_growth(curr_units, prev_one_month_units)
    yoy_units_pct = _calc_growth(curr_units, prev_year_units)

    pub_kpi = _fetch_best_publisher_kpis()
    best_publisher = pub_kpi["publisher"] if pub_kpi else "-"
    best_pub_curr_units = pub_kpi["units"]["latest"] if pub_kpi else None
    best_pub_units_text = _format_number(best_pub_curr_units) if best_pub_curr_units is not None else None

    prev_one_month_pub_units = pub_kpi["units"].get("prev_one_month") if pub_kpi else None
    prev_year_pub_units = pub_kpi["units"].get("prev_year") if pub_kpi else None

    mom_pub_units_pct = _calc_growth(best_pub_curr_units, prev_one_month_pub_units)
    yoy_pub_units_pct = _calc_growth(best_pub_curr_units, prev_year_pub_units)

    best_pub_subtitle = f"{best_pub_units_text} Units Sold" if best_pub_units_text else None

    cards = [
        _build_kpi_card(
            title="Total Revenue",
            value=f"{curr_revenue_value} JPY",
            subtitle=None,
            icon="bi:currency-dollar",
            yoy_delta=yoy_revenue_pct,
            mom_delta=mom_revenue_pct,
        ),
        _build_kpi_card(
            title="Total Units Sold",
            value=curr_units_value,
            subtitle=None,
            icon="bi:bag",
            yoy_delta=yoy_units_pct,
            mom_delta=mom_units_pct,
        ),
        _build_kpi_card(
            title="Best Publisher",
            value=best_publisher,
            subtitle=best_pub_subtitle,
            icon="bi:award",
            yoy_delta=yoy_pub_units_pct,
            mom_delta=mom_pub_units_pct,
        ),
    ]
    return html.Div(cards, className="kpi-grid")
