# app.py
from dash.dependencies import Input, Output, State
from dash import Dash, html, dcc # ← 多匯入 dcc
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

@app.callback(
    Output("global-end-ym", "options"),
    Output("global-end-ym", "value"),
    Input("global-start-ym", "value"),
    State("global-end-ym", "value"),
)
def update_end_options(start, end):
    # 全部月份（原本的）
    all_options = [
        f"{y}-{m:02d}"
        for y in range(2022, 2025)
        for m in range(1, 13)
        if not (y == 2024 and m > 12)
    ]

    # 建立所有 >= start 的選項
    end_options = [o for o in all_options if o >= start]

    # 如果原本 end < start，強制把 end 設成 start
    if end < start:
        end = start

    # 回傳成 Dash 用的格式
    return (
        [{"label": o, "value": o} for o in end_options],
        end,
    )

app.layout = dbc.Container(
    [
        # 頂部標題列 + 全局時間 filter
        dbc.Row(
            [
                # 左邊 Logo + Title
                dbc.Col(
                    dbc.Row(
                        [
                            dbc.Col(
                                html.Img(
                                    src = "/assets/logo.png",
                                    style={
                                        "height": "40px",
                                        "marginRight": "16px"
                                    }
                                ),
                                width = "auto",
                            ),
                            dbc.Col(
                                html.H1(
                                    "Sales Performance Dashboard",
                                    className = "dashboard-title",
                                    style = {"margin": "0"}
                                ),
                                width = "auto",
                            ),
                        ],
                        className = "align-items-center", # 這行非常重要，讓 Logo 與 Title 垂直置中
                    ),
                    md = 8,
                ),
            ],
            className = "align-items-center mb-4",
        ),
 
        # KPI 卡片
        kpi_cards.layout(),
        html.Hr(),

        dbc.Row(
            [
                # 左邊空白
                dbc.Col(
                    html.Div(
                        dcc.RadioItems(
                            id = "metric-toggle",
                            options=[
                                {"label": "Revenue", "value": "revenue"},
                                {"label": "Unit Sold", "value": "units"},
                            ],
                            value = "revenue",
                            inline = True,
                            className = "metric-toggle",
                        ),
                        style = {
                            "display": "flex",
                            "alignItems": "center",
                            "justifyContent": "flex-start",
                        },
                    ),
                    md = 8    
                ),

                # 右邊 Global Time Range
                dbc.Col(
                    html.Div(
                        [
                            html.Span("Time range", style = {"marginRight": "8px"}),

                            dcc.Dropdown(
                                id = "global-start-ym",
                                options = MONTH_OPTIONS,
                                value = "2022-01",
                                clearable = False,
                                searchable = False,
                                style = {
                                    "width": "120px",
                                    "display": "inline-block",
                                    "verticalAlign": "middle",
                                },
                            ),

                            html.Span(" → ", style = {"margin": "0 8px"}),

                            dcc.Dropdown(
                                id = "global-end-ym",
                                options = MONTH_OPTIONS,
                                value = "2024-12",
                                clearable = False,
                                searchable = False,
                                style = {
                                    "width": "120px",
                                    "display": "inline-block",
                                    "verticalAlign": "middle",
                                },
                            ),
                        ],
                        style = {
                            "display": "flex",
                            "flexDirection": "row",
                            "alignItems": "center",
                            "justifyContent": "flex-end",
                            "gap": "8px",
                        },
                    ),
                    md = 4,
                ),
            ]
        ),
        
        # 確保 layout 裡有這行
        dcc.Location(id = "url"),

        # Worst publishers + Top games pie
        publisher_overview.layout(),
        html.Hr(),

        # Genre / Publisher 趨勢
        line_charts.layout(),
        # html.Hr(),

        # Region 視覺化
        # map_chart.layout(),
    ],
    fluid = True,
    style = {"paddingLeft": "40px", "paddingRight": "40px", "paddingTop": "40px"},
)

if __name__ == "__main__":
    app.run(debug = True)
