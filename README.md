# Kadokawa Game Linkage – Sales Performance & Marketing Dashboard

Overview
--------
This project is an interactive analytics dashboard built with Dash, Plotly, and Bootstrap, designed for the Senior Regional Portfolio Manager at Kadokawa Game Linkage (KGL).
It provides tactical insights for monthly performance monitoring and short-term marketing decisions.

The dashboard includes KPIs, publisher-level analysis, genre performance trends, and regional comparisons.
The application entry point is `app.py`.

Quick start
-----------
1. Create and activate a Python virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run the app:
```bash
python3 app.py
```
Default address: http://127.0.0.1:8050

Project structure
-----------------
```
app.py                      # Dash application entry point
components/
│
├── kpi_cards.py            # Top-level KPI cards: revenue, units sold, best-selling publisher
│
├── publisher_overview.py   # Publisher treemap (Top/Worst 5) + game title pie chart
│
├── line_charts.py          # Genre trend line chart
│
└── bar_chart.py            # regional bar chart for game titles
│
utils/
└── query.py                # Helper functions for SQL queries and dataframe retrieval
|
data/
└── vgsales_30.db            # SQLite database used by the dashboard

```

Data description
----------------
The dashboard uses a SQLite database (`vgsales_30.db`) instead of the earlier CSV source.

Development notes
-----------------
- Add preprocessing scripts under `scripts/` or `utils/` to clean or aggregate data before visualization.
- Create new component modules in `components/` and import them in `app.py` to extend the UI.
- Consider caching or precomputing heavy aggregations for better performance.

Troubleshooting
---------------
- Blank page or errors: check the terminal for tracebacks and confirm `vgsales_30.db` path and column names.
- Missing styles: ensure `dash-bootstrap-components` is installed and the external stylesheet is loaded in `app.py`.

Contributing
------------
Fork the repo, create a branch for your feature/fix, add tests if applicable, and open a pull request describing changes.

Contact
-------
For guidance on components or data processing, specify the component or script to modify and desired outputs; instructions will be provided.