import geopandas as gpd
import json
from pathlib import Path

SRC = "assets/japan.geojson"
DST = "assets/japan_regions.geojson"

PREF_COL = "nam"

pref_to_region = {
    "Hokkai Do": "Hokkaido",
    "Aomori Ken": "Tohoku", "Iwate Ken": "Tohoku", "Miyagi Ken": "Tohoku",
    "Akita Ken": "Tohoku", "Yamagata Ken": "Tohoku", "Fukushima Ken": "Tohoku",

    "Ibaraki Ken": "Kanto", "Tochigi Ken": "Kanto", "Gunma Ken": "Kanto",
    "Saitama Ken": "Kanto", "Chiba Ken": "Kanto", "Tokyo To": "Kanto",
    "Kanagawa Ken": "Kanto",

    "Niigata Ken": "Chubu", "Toyama Ken": "Chubu", "Ishikawa Ken": "Chubu",
    "Fukui Ken": "Chubu", "Yamanashi Ken": "Chubu", "Nagano Ken": "Chubu",
    "Gifu Ken": "Chubu", "Shizuoka Ken": "Chubu", "Aichi Ken": "Chubu",

    "Mie Ken": "Kansai", "Shiga Ken": "Kansai", "Kyoto Fu": "Kansai",
    "Osaka Fu": "Kansai", "Hyogo Ken": "Kansai", "Nara Ken": "Kansai",
    "Wakayama Ken": "Kansai",

    "Tottori Ken": "Chugoku", "Shimane Ken": "Chugoku",
    "Okayama Ken": "Chugoku", "Hiroshima Ken": "Chugoku",
    "Yamaguchi Ken": "Chugoku",

    "Tokushima Ken": "Shikoku", "Kagawa Ken": "Shikoku",
    "Ehime Ken": "Shikoku", "Kochi Ken": "Shikoku",

    "Fukuoka Ken": "Kyushu", "Saga Ken": "Kyushu",
    "Nagasaki Ken": "Kyushu", "Kumamoto Ken": "Kyushu",
    "Oita Ken": "Kyushu", "Miyazaki Ken": "Kyushu",
    "Kagoshima Ken": "Kyushu", "Okinawa Ken": "Kyushu",
}

print("Loading prefecture geojson…")
gdf = gpd.read_file(SRC)

# mapping column
gdf["region_name"] = gdf[PREF_COL].map(pref_to_region)

missing = gdf[gdf["region_name"].isna()][PREF_COL].unique()
if len(missing):
    print("Unmapped prefectures:", missing)
    raise SystemExit

# Dissolve 成 8 大區域
print("Merging polygons…")
regions = gdf.dissolve(by="region_name", as_index=False)

# 輸出
regions.to_file(DST, driver="GeoJSON")
print(f"Generated: {DST}")
