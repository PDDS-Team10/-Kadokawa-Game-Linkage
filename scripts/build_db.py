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

NINTENDO_PLATFORMS = {
    "NES",
    "SNES",
    "N64",
    "GC",
    "GAMECUBE",
    "WII",
    "WIIU",
    "SWITCH",
    "3DS",
    "DS",
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

GENRE_REGION_PREFS = {
    "Role-Playing": {"Kanto": 1.2, "Kansai": 0.9},
    "Sports": {"Kansai": 1.25},
    "Shooter": {"Kyushu": 1.15, "Kanto": 1.05},
    "Platform": {"Kansai": 1.15, "Chubu": 1.1},
    "Action": {"Kanto": 1.05},
}

PUBLISHER_REGION_PREFS = {
    "nintendo": {"Kansai": 1.15, "Kanto": 1.1},
    "sony": {"Kanto": 1.15},
    "square": {"Kanto": 1.08},
}

def _month_from_ym(ym: str) -> int:
    """把 'YYYY-MM' 轉成對應月份數字"""
    return int(ym.split("-")[1])


assert abs(sum(REGION_WEIGHTS.values()) - 1.0) < 1e-6, "Region weights must sum to 1"


def parse_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _is_nintendo_platform(platform_name: str | None) -> bool:
    if not platform_name:
        return False
    return platform_name.upper() in NINTENDO_PLATFORMS


# 產生一個「先高後低」的 36 個月權重，模擬正常銷售週期
def generate_monthly_pattern(months, genre_name=None, publisher_name=None, platform_name=None):
    """
    給定月份區間，依 genre/publisher 偏好與生命週期型態，回傳總和 = 1 的月度權重。
    """
    num_months = len(months)
    if num_months == 0:
        return []

    seasonality = [BASE_SEASONALITY.get(_month_from_ym(ym), 1.0) for ym in months]

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
    if not fav_months:
        fav_months.append(random.randint(1, 12))

    target_month = random.choice(fav_months)
    candidate_indices = [
        idx for idx, ym in enumerate(months)
        if _month_from_ym(ym) == target_month
    ]
    main_idx = random.choice(candidate_indices) if candidate_indices else random.randint(0, num_months - 1)

    lifecycle_profiles = [
        {
            "name": "front",
            "decay_range": (2.0, 4.0),
            "main_strength": (1.3, 1.8),
            "bias": lambda idx, n: 1.25 - 0.8 * (idx / max(1, n - 1)),
        },
        {
            "name": "slow",
            "decay_range": (4.0, 7.0),
            "main_strength": (1.1, 1.4),
            "bias": lambda idx, n: 0.75 + 0.9 * (idx / max(1, n - 1)),
        },
        {
            "name": "long",
            "decay_range": (5.5, 9.0),
            "main_strength": (0.9, 1.2),
            "bias": lambda idx, n: 0.9 + 0.2 * math.sin((idx / max(1, n - 1)) * math.pi),
        },
    ]
    profile = random.choice(lifecycle_profiles)
    main_decay = random.uniform(*profile["decay_range"])
    main_strength = random.uniform(*profile["main_strength"])

    has_secondary = random.random() < 0.4
    if has_secondary:
        offset = max(1, num_months // random.randint(4, 6))
        direction = random.choice([-1, 1])
        secondary_idx = min(max(main_idx + direction * offset, 0), num_months - 1)
        secondary_decay = random.uniform(3.0, 6.5)
        secondary_strength = random.uniform(0.5, 1.0)
    else:
        secondary_idx = None
        secondary_decay = None
        secondary_strength = 0.0

    def peak_value(i, center, decay):
        if center is None or decay is None:
            return 0.0
        return math.exp(-((abs(i - center) / max(1e-3, decay)) ** 1.3))

    samples = []
    for idx in range(num_months):
        main_component = peak_value(idx, main_idx, main_decay)
        secondary_component = peak_value(idx, secondary_idx, secondary_decay)
        lifecycle_bias = max(0.2, profile["bias"](idx, num_months))
        alpha = seasonality[idx] * (
            0.6 + main_strength * main_component + secondary_strength * secondary_component
        )
        alpha *= lifecycle_bias * random.uniform(0.9, 1.05)
        alpha = max(0.15, alpha)
        samples.append(random.gammavariate(alpha, 1.0))

    # 移動平均平滑，避免單月尖峰
    smoothed = samples.copy()
    for idx in range(num_months):
        left = samples[idx - 1] if idx > 0 else samples[idx]
        mid = samples[idx]
        right = samples[idx + 1] if idx < num_months - 1 else samples[idx]
        smoothed[idx] = (left + 2 * mid + right) / 4.0

    # 再以動態範圍壓縮 (power < 1) 拉近高低落差
    avg = sum(smoothed) / num_months if num_months else 0
    compressed = []
    for value in smoothed:
        if avg <= 0:
            compressed.append(value)
            continue
        ratio = value / avg
        compressed.append(avg * (ratio ** 0.75))

    if _is_nintendo_platform(platform_name) or (publisher_name and "nintendo" in publisher_name.lower()):
        for idx, ym in enumerate(months):
            m = _month_from_ym(ym)
            if m == 10:
                compressed[idx] *= 1.2
            elif m == 11:
                compressed[idx] *= 1.5
            elif m == 12:
                compressed[idx] *= 1.8
            else:
                compressed[idx] *= 0.8

    total = sum(compressed)
    if total <= 0:
        return [1.0 / num_months] * num_months
    return [v / total for v in compressed]


def region_weight_distribution(
    platform_name: str | None,
    genre_name: str | None = None,
    publisher_name: str | None = None,
) -> dict[str, float]:
    """
    每款遊戲都會重新抽樣出一組地區權重，讓遊戲之間的地域表現更有個性。
    """
    base = REGION_WEIGHTS.copy()
    regions = list(base.keys())

    def biased_candidates():
        candidates = []
        for region, weight in base.items():
            candidates.extend([region] * max(1, int(weight * 100)))

        publisher_key = (publisher_name or "").lower()
        if "nintendo" in publisher_key:
            candidates.extend(["Kanto"] * 40 + ["Kansai"] * 35)
        if "sony" in publisher_key:
            candidates.extend(["Kanto"] * 30)

        genre_key = (genre_name or "").strip()
        if genre_key == "Racing":
            candidates.extend(["Kanto"] * 25 + ["Chubu"] * 20)
        elif genre_key == "Role-Playing":
            candidates.extend(["Kanto"] * 30)
        elif genre_key == "Sports":
            candidates.extend(["Kansai"] * 35)
        elif genre_key == "Shooter":
            candidates.extend(["Kyushu"] * 20 + ["Kanto"] * 15)
        elif genre_key == "Platform":
            candidates.extend(["Kansai"] * 25 + ["Chubu"] * 15)

        return candidates or regions

    candidates = biased_candidates()
    main_region = random.choice(candidates)
    secondary_region = None
    if random.random() < 0.4:
        secondary_choices = [r for r in regions if r != main_region]
        if secondary_choices:
            secondary_region = random.choice(secondary_choices)

    adjusted = base.copy()
    adjusted[main_region] *= random.uniform(2.0, 3.0)
    if secondary_region:
        adjusted[secondary_region] *= random.uniform(1.3, 1.8)

    weak_candidates = [r for r in regions if r not in {main_region, secondary_region}]
    weak_pick = random.sample(weak_candidates, k=min(len(weak_candidates), random.randint(1, 2))) if weak_candidates else []
    for region in weak_pick:
        adjusted[region] *= random.uniform(0.3, 0.7)

    for region in regions:
        if region not in weak_pick and region not in {main_region, secondary_region}:
            adjusted[region] *= random.uniform(0.8, 1.2)

    is_nintendo_title = _is_nintendo_platform(platform_name) or (publisher_name and "nintendo" in publisher_name.lower())
    if is_nintendo_title:
        for region in regions:
            if region in {"Kanto", "Kansai"}:
                adjusted[region] *= random.uniform(1.1, 1.3)
            else:
                adjusted[region] *= 0.9

    final = {region: adjusted[region] for region in regions}
    total = sum(final.values())
    if total <= 0:
        return base
    return {region: value / total for region, value in final.items()}


# 依平台類型給一個平均價格（JPY）
def base_price_for_platform(platform_name: str) -> int:
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


def price_for_game(platform_name: str, genre_name: str) -> int:
    """
    推估單款遊戲的建議售價，依平台基準價 + genre 係數 + 少量隨機。
    """
    base_price = base_price_for_platform(platform_name)
    genre_multipliers = {
        "Role-Playing": 1.3,
        "Simulation": 1.15,
        "Action": 1.1,
        "Shooter": 1.1,
        "Sports": 0.95,
        "Racing": 0.95,
        "Misc": 0.85,
    }
    factor = genre_multipliers.get(genre_name, 1.0)
    noise = random.uniform(0.9, 1.1)
    price = int(base_price * factor * noise)
    return int(round(price / 100.0)) * 100


def month_price_factor(month_index: int, total_months: int) -> float:
    """
    模擬價格隨時間逐步打折：首月較高，尾端較低。
    """
    if total_months <= 1:
        return 1.0
    t = month_index / (total_months - 1)
    return 1.1 - 0.5 * t


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
            year_month     TEXT    NOT NULL,  -- 例如 '2023-01'
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

    # 36 個月份：2023-01 ~ 2025-12
    months = []
    year = 2023
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
        price_jpy = price_for_game(platform, genre_name)

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

        if publisher_name == "Nintendo":
            if genre_name == "Platform":
                base_japan_m *= random.uniform(1.55, 1.7)  # 讓任天堂平台類強勢
            else:
                base_japan_m *= random.uniform(0.88, 0.95)  # 其他任天堂 genre 略微收斂

        region_weights = region_weight_distribution(platform, genre_name, publisher_name)

        # ===== 拆成 8 區 → SALE & SaleMonthly =====
        for region_name, weight in region_weights.items():
            region_id = region_ids[region_name]

            # lifetime：該區的百萬銷量與實際片數
            region_sales_m = round(base_japan_m * weight, 4)
            region_sales_units = int(region_sales_m * 1_000_000)

            if region_sales_units <= 0:
                continue

            # lifetime revenue 仍用建議售價估算，月度銷售再施加折扣
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
                platform_name=platform,
            )
            total_months = len(months)

            for idx, (ym, w) in enumerate(zip(months, monthly_weights)):
                month_sales_m = round(region_sales_m * w, 5)
                month_units = int(region_sales_units * w)
                if month_units <= 0:
                    continue

                factor = month_price_factor(idx, total_months)
                month_price_jpy = int(price_jpy * factor)
                month_revenue = month_units * month_price_jpy

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
