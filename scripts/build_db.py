import csv
import math
import random
import sqlite3
from pathlib import Path

INPUT_CSV = "data/vgsales_30.csv"
SQLITE_DB = "data/vgsales_30.db"

# === 日本八區權重（總和 = 1） ===
REGION_WEIGHTS = {
    "Hokkaido": 0.04,
    "Tohoku": 0.06,
    "Kanto": 0.35,
    "Chubu": 0.17,
    "Kansai": 0.18,
    "Chugoku": 0.06,
    "Shikoku": 0.04,
    "Kyushu": 0.10,
}

# === 月份季節性（越大代表越容易有銷售） ===
# 「整體市場」的 baseline
BASE_SEASONALITY = {
    1: 0.9,   # 新年後有點冷
    2: 0.85,
    3: 0.95,
    4: 1.00,
    5: 1.05,
    6: 1.10,
    7: 1.20,  # 暑假檔期
    8: 1.15,
    9: 1.05,
    10: 1.10,
    11: 1.25, # 年末衝一波
    12: 1.40, # 聖誕 ＋ 跨年大檔
}

# 各 genre 偏好的「主高峰月份」
GENRE_PEAK_MONTH = {
    "Sports": 9,          # 運動遊戲：秋季開賽
    "Racing": 6,          # 賽車：暑假前後
    "Shooter": 11,        # 射擊：年底大作多
    "Action": 11,
    "Fighting": 7,
    "Role-Playing": 2,    # RPG：寒假 / 春節檔
    "Simulation": 4,
    "Platform": 10,
    "Misc": 5,
}

# 某些大廠的年底 or 特定習慣
PUBLISHER_PEAK_MONTH = {
    "Nintendo": 11,
    "Sony": 3,                    # Sony Computer Entertainment
    "Square": 12,                 # Square Enix etc.
    "Namco": 7,                   # Bandai Namco
    "Capcom": 2,
    "Ubisoft": 10,
}

def _month_from_ym(ym: str) -> int:
    """把 '2022-07' 轉成 7"""
    return int(ym.split("-")[1])


assert abs(sum(REGION_WEIGHTS.values()) - 1.0) < 1e-6, "Region weights must sum to 1"


def parse_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


# 產生一個「先高後低」的 36 個月權重，模擬正常銷售週期
def generate_monthly_pattern(months, genre_name=None, publisher_name=None):
    """
    給定 36 個 year_month（2022-01 ~ 2024-12），
    回傳每個月份的權重（總和 = 1）

    組成 = 市場季節性 × (該 game 的高峰曲線) × 一點隨機 noise
    再依 genre / publisher 去偏移高峰位置。
    """
    num_months = len(months)
    if num_months == 0:
        return []

    # 基本季節性：只看 month（1~12）
    base = []
    for ym in months:
        m = _month_from_ym(ym)
        base.append(BASE_SEASONALITY.get(m, 1.0))

    # 決定「理論高峰月」：genre / publisher 共同影響
    fav_months = []

    if genre_name:
        g = genre_name.strip()
        if g in GENRE_PEAK_MONTH:
            fav_months.append(GENRE_PEAK_MONTH[g])

    if publisher_name:
        pname = publisher_name.lower()
        for key, m in PUBLISHER_PEAK_MONTH.items():
            if key.lower() in pname:
                fav_months.append(m)
                break

    # 如果兩邊都沒有偏好，就隨機在 1~12 選一個月
    if not fav_months:
        fav_months.append(random.randint(1, 12))

    target_month = random.choice(fav_months)

    # 找出這個 target_month 在 36 個 month 中對應到的 index 們
    candidate_indices = [
        idx for idx, ym in enumerate(months)
        if _month_from_ym(ym) == target_month
    ]
    if candidate_indices:
        peak_idx = random.choice(candidate_indices)
    else:
        peak_idx = random.randint(0, num_months - 1)

    # 為這款遊戲產生一條「以 peak_idx 為中心的衰退曲線」
    decay = random.uniform(4.0, 10.0)  # 越大越平緩
    curve = []
    for i in range(num_months):
        d = abs(i - peak_idx)
        local = math.exp(-d / decay)
        curve.append(local)

    # 把季節性 × 曲線 × noise 合併
    combined = []
    for i in range(num_months):
        noise = random.uniform(0.85, 1.15)  # 每個月一點隨機起伏
        combined.append(base[i] * curve[i] * noise)

    total = sum(combined)
    if total <= 0:
        return [1.0 / num_months] * num_months

    return [v / total for v in combined]



# 依平台類型給一個平均價格（JPY）
def price_for_platform(platform_name: str) -> int:
    platform_name = platform_name.upper()

    home_consoles = {
        "WII", "NES", "SNES", "N64", "GC",
        "PS", "PS2", "PS3", "PS4",
        "X360", "XB", "XONE",
    }
    handhelds = {"GB", "GBA", "DS", "3DS", "PSP", "PSV"}
    pcs = {"PC"}

    if platform_name in home_consoles:
        return 6800
    if platform_name in handhelds:
        return 4800
    if platform_name in pcs:
        return 5980
    return 6000  # default


def init_db():
    db_path = Path(SQLITE_DB)
    if db_path.exists():
        db_path.unlink()

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # === 建表：對應 ERD，外加 sales_units + revenue_jpy ===
    cur.executescript(
        """
        PRAGMA foreign_keys = ON;

        CREATE TABLE PLATFORM (
            platform_id   INTEGER PRIMARY KEY AUTOINCREMENT,
            platform_name TEXT NOT NULL UNIQUE
        );

        CREATE TABLE REGION (
            region_id   INTEGER PRIMARY KEY AUTOINCREMENT,
            region_name TEXT NOT NULL UNIQUE,
            region_code TEXT NOT NULL UNIQUE
        );

        CREATE TABLE GENRE (
            genre_id   INTEGER PRIMARY KEY AUTOINCREMENT,
            genre_name TEXT NOT NULL UNIQUE
        );

        CREATE TABLE PUBLISHER (
            publisher_id   INTEGER PRIMARY KEY AUTOINCREMENT,
            publisher_name TEXT NOT NULL UNIQUE
        );

        CREATE TABLE GAME (
            game_id      INTEGER PRIMARY KEY AUTOINCREMENT,
            game_name    TEXT NOT NULL,
            release_year INTEGER,
            genre_id     INTEGER NOT NULL,
            publisher_id INTEGER NOT NULL,
            FOREIGN KEY (genre_id)     REFERENCES GENRE(genre_id),
            FOREIGN KEY (publisher_id) REFERENCES PUBLISHER(publisher_id)
        );

        -- lifetime：每款 game × platform × region
        CREATE TABLE SALE (
            game_id        INTEGER NOT NULL,
            platform_id    INTEGER NOT NULL,
            region_id      INTEGER NOT NULL,
            sales_million  REAL    NOT NULL,  -- 原始單位：百萬片
            sales_units    INTEGER NOT NULL,  -- 實際片數
            revenue_jpy    INTEGER NOT NULL,  -- 營收（日圓）
            PRIMARY KEY (game_id, platform_id, region_id),
            FOREIGN KEY (game_id)     REFERENCES GAME(game_id),
            FOREIGN KEY (platform_id) REFERENCES PLATFORM(platform_id),
            FOREIGN KEY (region_id)   REFERENCES REGION(region_id)
        );

        -- 36 個月拆分：game × platform × region × month
        CREATE TABLE SaleMonthly (
            game_id        INTEGER NOT NULL,
            platform_id    INTEGER NOT NULL,
            region_id      INTEGER NOT NULL,
            year_month     TEXT    NOT NULL,  -- 例如 '2022-01'
            sales_million  REAL    NOT NULL,
            sales_units    INTEGER NOT NULL,
            revenue_jpy    INTEGER NOT NULL,
            PRIMARY KEY (game_id, platform_id, region_id, year_month),
            FOREIGN KEY (game_id)     REFERENCES GAME(game_id),
            FOREIGN KEY (platform_id) REFERENCES PLATFORM(platform_id),
            FOREIGN KEY (region_id)   REFERENCES REGION(region_id)
        );
        """
    )

    conn.commit()
    return conn


def seed_regions(cur):
    regions = [
        ("Hokkaido", "HKD"),
        ("Tohoku", "THK"),
        ("Kanto", "KNT"),
        ("Chubu", "CHB"),
        ("Kansai", "KNS"),
        ("Chugoku", "CHG"),
        ("Shikoku", "SHK"),
        ("Kyushu", "KYS"),
    ]
    cur.executemany(
        "INSERT INTO REGION (region_name, region_code) VALUES (?, ?);",
        regions,
    )

    cur.execute("SELECT region_id, region_name FROM REGION;")
    return {name: rid for (rid, name) in cur.fetchall()}


def build_from_csv(conn):
    input_path = Path(INPUT_CSV)
    if not input_path.exists():
        raise FileNotFoundError(f"找不到輸入檔案: {input_path}")

    cur = conn.cursor()

    with input_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    platform_ids = {}
    genre_ids = {}
    publisher_ids = {}
    game_ids = {}

    region_ids = seed_regions(cur)

    # 36 個月份：2022-01 ~ 2024-12
    months = []
    year = 2022
    month = 1
    for _ in range(36):
        months.append(f"{year:04d}-{month:02d}")
        month += 1
        if month > 12:
            month = 1
            year += 1

    for row in rows:
        name = row["Name"].strip()
        platform = row["Platform"].strip()
        year_val = int(row["Year"])
        genre_name = row["Genre"].strip()
        publisher_name = row["Publisher"].strip()

        # ===== PLATFORM =====
        if platform not in platform_ids:
            cur.execute(
                "INSERT INTO PLATFORM (platform_name) VALUES (?);",
                (platform,),
            )
            platform_ids[platform] = cur.lastrowid
        platform_id = platform_ids[platform]

        # 該平台的平均價格
        price_jpy = price_for_platform(platform)

        # ===== GENRE =====
        if genre_name not in genre_ids:
            cur.execute(
                "INSERT INTO GENRE (genre_name) VALUES (?);",
                (genre_name,),
            )
            genre_ids[genre_name] = cur.lastrowid
        genre_id = genre_ids[genre_name]

        # ===== PUBLISHER =====
        if publisher_name not in publisher_ids:
            cur.execute(
                "INSERT INTO PUBLISHER (publisher_name) VALUES (?);",
                (publisher_name,),
            )
            publisher_ids[publisher_name] = cur.lastrowid
        publisher_id = publisher_ids[publisher_name]

        # ===== GAME =====
        game_key = (name, year_val, publisher_name)
        if game_key not in game_ids:
            cur.execute(
                """
                INSERT INTO GAME (game_name, release_year, genre_id, publisher_id)
                VALUES (?, ?, ?, ?);
                """,
                (name, year_val, genre_id, publisher_id),
            )
            game_ids[game_key] = cur.lastrowid
        game_id = game_ids[game_key]

        # ===== JP 總銷售量（百萬片，若 0 則 fallback 用 Global）=====
        jp_sales_m = parse_float(row.get("JP_Sales", 0.0))
        global_sales_m = parse_float(row.get("Global_Sales", 0.0))
        base_japan_m = jp_sales_m if jp_sales_m > 0 else global_sales_m

        if base_japan_m <= 0:
            continue

        # ===== 拆成 8 區 → SALE & SaleMonthly =====
        for region_name, weight in REGION_WEIGHTS.items():
            region_id = region_ids[region_name]

            # lifetime：該區的百萬銷量與實際片數
            region_sales_m = round(base_japan_m * weight, 4)
            region_sales_units = int(region_sales_m * 1_000_000)

            if region_sales_units <= 0:
                continue

            region_revenue = region_sales_units * price_jpy

            cur.execute(
                """
                INSERT INTO SALE
                    (game_id, platform_id, region_id,
                     sales_million, sales_units, revenue_jpy)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    game_id,
                    platform_id,
                    region_id,
                    region_sales_m,
                    region_sales_units,
                    region_revenue,
                ),
            )

            # 36 個月拆分：考慮季節 + genre + publisher
            monthly_weights = generate_monthly_pattern(
                months,
                genre_name=genre_name,
                publisher_name=publisher_name,
            )

            for ym, w in zip(months, monthly_weights):
                month_sales_m = round(region_sales_m * w, 5)
                month_units = int(region_sales_units * w)
                if month_units <= 0:
                    continue

                month_revenue = month_units * price_jpy

                cur.execute(
                    """
                    INSERT INTO SaleMonthly
                        (game_id, platform_id, region_id,
                         year_month, sales_million, sales_units, revenue_jpy)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        game_id,
                        platform_id,
                        region_id,
                        ym,
                        month_sales_m,
                        month_units,
                        month_revenue,
                    ),
                )

    conn.commit()


if __name__ == "__main__":
    conn = init_db()
    build_from_csv(conn)
    conn.close()
    print(f"[OK] SQLite DB 已建立：{SQLITE_DB}")
