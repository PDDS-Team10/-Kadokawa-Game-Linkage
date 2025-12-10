# -----------------------------------------------------------------------------
# Japan Region Choropleth Component
#
# This component renders a choropleth map of Japan regions using Mapbox.
# It supports:
#   - Global date range filters (`global-start-ym`, `global-end-ym`).
#   - Metric toggle from another component: "revenue" / "units".
#   - An additional filter dimension: "all" / "publisher" / "platform"
#     with a dependent dropdown to choose specific publisher/platform.
#
# For teammates:
# - If you only want to adjust the layout (height, text, spacing), look at `layout()`.
# - If you want to change how we query / aggregate data, check `_region_choropleth_fig`.
# - If you want to add another filter dimension (e.g. "Genre"), you can:
#     1. Extend `_region_choropleth_fig` to handle dim == "genre".
#     2. Update `update_region_filter_options` to provide genre options.
#     3. Update any UI labels in `layout()`.
# -----------------------------------------------------------------------------

import json
from pathlib import Path
from dash import dcc, html, callback
import plotly.express as px
from dash.dependencies import Input, Output

from utils.query import read_df

GEOJSON_PATH = Path("assets/japan_regions.geojson")

# Load Japan regions GeoJSON only once at import time
with GEOJSON_PATH.open("r", encoding="utf-8") as f:
    JP_REGIONS_GEOJSON = json.load(f)


def _region_choropleth_fig(
    start_ym: str,
    end_ym: str,
    metric: str,
    dim: str = "all",
    filter_value: str | None = None,
):
    """
    Build the choropleth figure for Japan regions.

    Notes
    -----
    - If `dim` is "publisher" or "platform" but `filter_value` is still None
      (e.g., user hasn’t picked from the dropdown yet), we fall back to "all"
      to avoid building an invalid SQL query.
    """
    # 避免 dim = publisher/platform 但還沒選 dropdown 時炸掉
    if dim in ("publisher", "platform") and not filter_value:
        dim = "all"

    # Choose which metric column to aggregate
    if metric == "units":
        value_col = "sales_units"
        value_label = "Units Sold"
    else:
        value_col = "revenue_jpy"
        value_label = "Revenue (JPY)"

    # Build SQL query with optional joins + where clauses
    base_sql = f"""
        SELECT
            r.region_name,
            SUM(m.{value_col}) AS value
        FROM SaleMonthly m
        JOIN REGION r ON m.region_id = r.region_id
    """

    where_clauses = ["m.year_month BETWEEN ? AND ?"]
    params = [start_ym, end_ym]

    # 若有篩選：加上 join + where
    if dim == "publisher":
        base_sql += """
            JOIN GAME g ON m.game_id = g.game_id
            JOIN PUBLISHER p ON g.publisher_id = p.publisher_id
        """
        where_clauses.append("p.publisher_name = ?")
        params.append(filter_value)

    elif dim == "platform":
        base_sql += """
            JOIN PLATFORM pl ON m.platform_id = pl.platform_id
        """
        where_clauses.append("pl.platform_name = ?")
        params.append(filter_value)

    sql = (
        base_sql
        + " WHERE "
        + " AND ".join(where_clauses)
        + " GROUP BY r.region_name"
    )

    df = read_df(sql, params)

    # Build choropleth mapbox figure
    fig = px.choropleth_mapbox(
        df,
        geojson=JP_REGIONS_GEOJSON,
        locations="region_name",
        featureidkey="properties.region_name",  # 對到 GeoJSON 裡的欄位
        color="value",
        color_continuous_scale="Blues",
        mapbox_style="carto-positron",
        center={"lat": 36.5, "lon": 138.0},
        zoom=4.0,
        opacity=0.7,
        labels={"value": value_label},
    )

    # Layout tuning:
    # 1. Fix center & zoom level (in case Plotly tries to adjust dynamically)
    # 2. Disable drag so users can hover to see tooltip but cannot move the map
    fig.update_layout(
        margin=dict(l=0, r=0, t=0, b=0),
        mapbox=dict(
            center={"lat": 36.5, "lon": 138.0},
            zoom=4.0,
        ),
    )

    return fig

# -------Callbacks-------
@callback(
    Output("region-map-graph", "figure"),
    Input("global-start-ym", "value"),
    Input("global-end-ym", "value"),
    Input("trend-metric-toggle", "value"),   # "revenue" / "units"
    Input("region-dim-toggle", "value"),     # "all" / "publisher" / "platform"
    Input("region-filter-dropdown", "value") # publisher_name / platform_name / None
)
def update_region_map(start_ym, end_ym, metric, dim, filter_value):
    """
    Main callback to update the Japan region map.
    """
    return _region_choropleth_fig(start_ym, end_ym, metric, dim, filter_value)

@callback(
    Output("region-filter-dropdown", "options"),
    Output("region-filter-dropdown", "value"),
    Output("region-filter-dropdown", "placeholder"),
    Output("region-filter-dropdown", "disabled"),
    Input("region-dim-toggle", "value"),
)

def update_region_filter_options(dim):
    """
    Update dropdown options based on the selected dimension.
    """
    # All：不顯示任何選項、也不能點
    if dim == "all":
        return [], None, "Select publisher / platform", True

    if dim == "publisher":
        sql = "SELECT DISTINCT publisher_name FROM PUBLISHER ORDER BY publisher_name;"
        df = read_df(sql)
        options = [
            {"label": name, "value": name}
            for name in df["publisher_name"].tolist()
        ]
        return options, None, "Select publisher", False

    if dim == "platform":
        sql = "SELECT DISTINCT platform_name FROM PLATFORM ORDER BY platform_name;"
        df = read_df(sql)
        options = [
            {"label": name, "value": name}
            for name in df["platform_name"].tolist()
        ]
        return options, None, "Select platform", False

# -------Layout-------
def layout():
    """
    Layout for the Japan regional overview section.

    In comments:
    1. 想改標題、說明文字，可以直接改 H2 / P
    2. 想調整整體高度，可以改 `dcc.Graph` 的 style.height
    3. 如果你想在小螢幕讓 filter 區從左右排列變成上下排列，可以把最外層 filter row 的 `display: "flex"` 改成 column 之類的
    """
    return html.Div(
        [
            html.H2("Japan Regional Overview"),
            html.P("Regional Performance – Revenue / Units"),

            # === Filter ===
            html.Div(
                [
                    # 切換 All / Publisher / Platform
                    html.Div(
                        [
                            html.Label("Filter by:"),
                            dcc.RadioItems(
                                id="region-dim-toggle",
                                options=[
                                    {"label": "All", "value": "all"},
                                    {"label": "Publisher", "value": "publisher"},
                                    {"label": "Platform", "value": "platform"},
                                ],
                                value="all",
                                inline=True,
                            ),
                        ],
                        style={"display": "flex", "gap": "1rem", "alignItems": "center"},
                    ),

                    # 依 dim 顯示不同選項的 Dropdown
                    html.Div(
                        [
                            dcc.Dropdown(
                                id="region-filter-dropdown",
                                placeholder="Select publisher / platform",
                                clearable=True,
                            )
                        ],
                        style={"width": "280px"},
                    ),
                ],
                style={
                    "display": "flex",
                    "justifyContent": "space-between",
                    "alignItems": "flex-end",
                    "marginBottom": "1rem",
                },
            ),

            # Japan region choropleth map
            dcc.Graph(
                id="region-map-graph",
                style={"height": "550px"},
                config={
                    "staticPlot": False,   # 保留 hover 互動
                    "scrollZoom": False,   # 禁止滑鼠滾輪縮放
                    "doubleClick": False,  # 雙擊不要亂 zoom
                },
            )
        ]
    )