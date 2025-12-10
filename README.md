# Kadokawa Game Linkage – Distribution Dashboard

Overview
--------
An interactive dashboard built with Dash and Bootstrap that visualizes video game sales data (KPI cards, publisher overview, genre/publisher trends, and regional maps). The app entry point is `app.py`.

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
- app.py — Dash application entry
- components/
  - kpi_cards.py — KPI card components
  - publisher_overview.py — Worst/top publisher and pie charts
  - line_charts.py — Genre / publisher trend charts
  - map_chart.py — Regional visualization
- data/
  - vgsales.csv — Original video game sales dataset

Data description
----------------
CSV columns: Rank, Name, Platform, Year, Genre, Publisher, NA_Sales, EU_Sales, JP_Sales, Other_Sales, Global_Sales. Data is used to compute KPIs, aggregate trends, and map visualizations.

Development notes
-----------------
- Add preprocessing scripts under `scripts/` or `utils/` to clean or aggregate data before visualization.
- Create new component modules in `components/` and import them in `app.py` to extend the UI.
- Consider caching or precomputing heavy aggregations for better performance.

Troubleshooting
---------------
- Blank page or errors: check the terminal for tracebacks and confirm `vgsales.csv` path and column names.
- Missing styles: ensure `dash-bootstrap-components` is installed and the external stylesheet is loaded in `app.py`.

Contributing
------------
Fork the repo, create a branch for your feature/fix, add tests if applicable, and open a pull request describing changes.

Contact
-------
For guidance on components or data processing, specify the component or script to modify and desired outputs; instructions will be provided.