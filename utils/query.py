# utils/query.py
from pathlib import Path
import sqlite3
import pandas as pd

# 專案根目錄 / data / vgsales_30.db
BASE_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BASE_DIR / "data" / "vgsales_30.db"


def get_connection():
    """回傳一個 sqlite3.Connection，呼叫者負責關閉。"""
    conn = sqlite3.connect(DB_PATH)
    return conn


def read_df(sql: str, params=None) -> pd.DataFrame:
    """執行查詢並以 DataFrame 回傳。"""
    if params is None:
        params = []
    conn = get_connection()
    try:
        df = pd.read_sql_query(sql, conn, params=params)
    finally:
        conn.close()
    return df
