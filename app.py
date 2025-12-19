# app.py
from dash.dependencies import Input, Output, State
from dash import Dash, html, dcc, callback_context
import dash_bootstrap_components as dbc

from components import kpi_cards, publisher_overview, line_charts, map_chart

MONTH_OPTIONS = [
    {"label": f"{y}-{m:02d}", "value": f"{y}-{m:02d}"}
    for y in range(2023, 2026)
    for m in range(1, 13)
]

app = Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
)
server = app.server
app.title = "Kadokawa Game Dashboard"


@app.callback(
    Output("global-end-ym", "options"),
    Output("global-end-ym", "value"),
    Input("global-start-ym", "value"),
    State("global-end-ym", "value"),
)
def update_end_options(start, end):
    all_options = [
        f"{y}-{m:02d}"
        for y in range(2023, 2026)
        for m in range(1, 13)
    ]
    end_options = [o for o in all_options if o >= start]
    if end < start:
        end = start
    return (
        [{"label": o, "value": o} for o in end_options],
        end,
    )


app.layout = dbc.Container(
    [
        html.Div(
            className="dashboard-header",
            children=[
                html.Div(
                    className="dashboard-brand",
                    children=[
                        html.Img(src="/assets/kd_logo.png", className="dashboard-logo"),
                        html.Div("Sales Performance Dashboard", className="dashboard-title"),
                    ],
                ),
            ],
        ),
        kpi_cards.layout(),
        html.Div(
            className="global-filters-row",
            children=[
                html.Div(
                    id="metric-toggle-pill",
                    className="metric-toggle-pill metric-toggle-revenue-active",
                    children=[
                        html.Div(className="metric-slider"),
                        html.Button("Revenue", id="metric-tab-revenue", className="metric-tab metric-tab-left"),
                        html.Button("Unit Sold", id="metric-tab-units", className="metric-tab metric-tab-right"),
                        dcc.RadioItems(
                            id="metric-toggle",
                            options=[
                                {"label": "Revenue", "value": "revenue"},
                                {"label": "Unit Sold", "value": "units"},
                            ],
                            value="revenue",
                            style={"display": "none"},
                        ),
                    ],
                ),
                html.Div(
                    className="date-range-pill",
                    children=[
                        dcc.Dropdown(
                            id="global-start-ym",
                            options=MONTH_OPTIONS,
                            value="2023-01",
                            clearable=False,
                            searchable=False,
                            className="date-pill-dropdown",
                        ),
                        html.Span("—", className="date-range-separator"),
                        dcc.Dropdown(
                            id="global-end-ym",
                            options=MONTH_OPTIONS,
                            value="2025-12",
                            clearable=False,
                            searchable=False,
                            className="date-pill-dropdown",
                        ),
                        html.Span(className="date-range-icon"),
                    ],
                ),
            ],
        ),
        dcc.Location(id="url"),
        html.Div(
            id="publishers-section-card",
            className="publishers-card",
            children=[
                publisher_overview.layout(),
                html.Div(
                    line_charts.layout(),
                    style={
                        "backgroundColor": "white",
                        "borderRadius": "24px",
                        "padding": "24px",
                        "marginTop": "24px",
                        "boxShadow": "0 4px 12px rgba(15, 23, 42, 0.04)",
                    },
                ),
            ],
        ),
        # map_chart.layout(),
    ],
    fluid=True,
    style={"paddingLeft": "40px", "paddingRight": "40px", "paddingTop": "40px"},
)


@app.callback(
    Output("metric-toggle", "value"),
    Output("metric-toggle-pill", "className"),
    Input("metric-tab-revenue", "n_clicks"),
    Input("metric-tab-units", "n_clicks"),
    State("metric-toggle", "value"),
)
def switch_metric(revenue_clicks, units_clicks, current_value):
    ctx = callback_context
    selected = current_value or "revenue"
    if ctx.triggered:
        trigger = ctx.triggered[0]["prop_id"].split(".")[0]
        if trigger == "metric-tab-revenue":
            selected = "revenue"
        elif trigger == "metric-tab-units":
            selected = "units"

    pill_class = (
        "metric-toggle-pill metric-toggle-revenue-active"
        if selected == "revenue"
        else "metric-toggle-pill metric-toggle-units-active"
    )
    return selected, pill_class


if __name__ == "__main__":
    app.run(debug=True)
