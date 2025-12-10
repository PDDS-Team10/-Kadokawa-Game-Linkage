# app.py
from dash import Dash, html, dcc     # ← 多匯入 dcc
import dash_bootstrap_components as dbc

from components import kpi_cards, publisher_overview, line_charts, map_chart

MONTH_OPTIONS = [
    {"label": f"{y}-{m:02d}", "value": f"{y}-{m:02d}"}
    for y in range(2022, 2025)
    for m in range(1, 13)
    if not (y == 2024 and m > 12)
]

app = Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
)
app.title = "Kadokawa Game Dashboard"

app.layout = dbc.Container(
    [
        # 頂部標題列 + 全局時間 filter
        dbc.Row(
            [
                dbc.Col(
                    html.H1(
                        "Kadokawa Game Linkage – Distribution Dashboard",
                        className="my-4",
                    ),
                    md=8,
                ),
                dbc.Col(
                    html.Div(
                        [
                            html.Span("Time range", style={"marginRight": "8px"}),
                            dcc.Dropdown(
                                id="global-start-ym",
                                options=MONTH_OPTIONS,
                                value="2022-01",
                                clearable=False,
                                style={"width": "110px", "display": "inline-block"},
                            ),
                            html.Span(" → ", style={"margin": "0 6px"}),
                            dcc.Dropdown(
                                id="global-end-ym",
                                options=MONTH_OPTIONS,
                                value="2024-12",
                                clearable=False,
                                style={"width": "110px", "display": "inline-block"},
                            ),
                        ],
                        style={
                            "textAlign": "right",
                            "marginTop": "24px",
                        },
                    ),
                    md=4,
                ),
            ],
            className="align-items-center",
        ),

        # KPI 卡片
        kpi_cards.layout(),
        html.Hr(),

        # Worst publishers + Top games pie
        publisher_overview.layout(),
        html.Hr(),

        # Genre / Publisher 趨勢
        line_charts.layout(),
        html.Hr(),

        # Region 視覺化
        map_chart.layout(),
    ],
    fluid=True,
)

if __name__ == "__main__":
    app.run(debug=True)
