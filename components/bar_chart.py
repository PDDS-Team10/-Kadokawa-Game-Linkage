from dash import html, dcc, Input, Output, callback
import plotly.express as px
import textwrap

from utils.query import read_df

GENRE_LIST = [
    "Action",
    "Adventure",
    "Fighting",
    "Misc",
    "Platform",
    "Racing",
    "Role-Playing",
    "Shooter",
    "Simulation",
    "Sports",
]


def _normalize_month_range(start_ym, end_ym):
    if not start_ym:
        start_ym = "2023-01"
    if not end_ym:
        end_ym = "2025-12"
    if start_ym > end_ym:
        start_ym, end_ym = end_ym, start_ym
    return start_ym, end_ym


def _genre_bar_df(genre, publisher, start_ym, end_ym):
    sql = """
    SELECT 
        r.region_name AS region,
        g.game_name,
        SUM(m.revenue_jpy) AS revenue,
        SUM(m.sales_units) AS units
    FROM SaleMonthly m
    JOIN GAME g          ON m.game_id = g.game_id
    JOIN GENRE ge        ON g.genre_id = ge.genre_id
    JOIN PUBLISHER p     ON g.publisher_id = p.publisher_id
    JOIN REGION r        ON m.region_id = r.region_id
    WHERE ge.genre_name = ?
      AND p.publisher_name = ?
      AND m.year_month BETWEEN ? AND ?
    GROUP BY r.region_name, g.game_name
    ORDER BY r.region_name, g.game_name;
    """
    return read_df(sql, [genre, publisher, start_ym, end_ym])


def _genre_bar_fig(df, genre, metric):
    if df.empty:
        fig = px.bar(title=f"No data for {genre}")
        fig.update_layout(
            xaxis_title="Region",
            yaxis_title=metric.capitalize(),
            margin=dict(l=20, r=20, t=40, b=20),
        )
        return fig

    y_col = "revenue" if metric == "revenue" else "units"
    custom_colors = [
        "#1E2A78",
        "#2E4A9E",
        "#4F6CC4",
        "#7B8FE1",
        "#A7B2F7",
        "#C9D1FF",
        "#E0E7FF",
    ]

    region_rank = (
        df.groupby("region")[y_col]
        .sum()
        .sort_values(ascending=False)
        .head(5)
        .index.tolist()
    )
    df = df[df["region"].isin(region_rank)]

    title_rank = (
        df.groupby("game_name")[y_col]
        .sum()
        .sort_values(ascending=False)
        .head(3)
        .index.tolist()
    )
    df = df[df["game_name"].isin(title_rank)]

    fig = px.bar(
        df,
        x="region",
        y=y_col,
        color="game_name",
        barmode="group",
        title=None,
        color_discrete_sequence=custom_colors,
    )

    # Wrap legend labels so long game names don't push the legend too wide
    for trace in fig.data:
        trace.name = "<br>".join(textwrap.wrap(trace.name, width=20)) or trace.name

    fig.update_layout(
        xaxis_title="Region",
        yaxis_title="Revenue (JPY)" if metric == "revenue" else "Units Sold",
        margin=dict(l=24, r=160, t=34, b=60),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        bargap=0.2,
        legend=dict(
            title_text="",
            orientation="v",
            font=dict(size=11),
            x=1.02,
            xanchor="left",
            y=1,
            yanchor="top",
            itemsizing="trace",
            itemwidth=80,
            tracegroupgap=4,
        ),
        yaxis=dict(showgrid=True, gridcolor="rgba(0,0,0,0.06)"),
        xaxis=dict(showgrid=False, domain=[0, 2/3], automargin=True),
        height=340,
    )
    return fig


def layout():
    return html.Div(
        [
            html.H3(
                "Game Title Performance",
                style={
                    "margin": "0 0 12px",
                    "textAlign": "center",
                    "color": "#1e2553",
                    "fontSize": "32px",
                    "whiteSpace": "nowrap",
                },
            ),
            dcc.Dropdown(
                id="genre-bar-select",
                options=[{"label": g, "value": g} for g in GENRE_LIST],
                value=GENRE_LIST[0],
                clearable=False,
                className="pill-dropdown pill-dropdown--single",
                style={"width": "220px", "margin": "0 auto 12px"},
            ),
            dcc.Graph(id="genre-bar-graph", style={"height": "440px", "width": "100%"}),
        ],
        style={"flex": 1},
    )


@callback(
    Output("genre-bar-graph", "figure"),
    Input("genre-bar-select", "value"),
    Input("trend-publisher-select", "value"),
    Input("metric-toggle", "value"),
    Input("global-start-ym", "value"),
    Input("global-end-ym", "value"),
)
def update_genre_bar_chart(genre, publisher, metric, start_ym, end_ym):
    start_ym, end_ym = _normalize_month_range(start_ym, end_ym)
    df = _genre_bar_df(genre, publisher, start_ym, end_ym)
    metric_label = "units" if metric == "units" else "revenue"
    return _genre_bar_fig(df, genre, metric_label)
