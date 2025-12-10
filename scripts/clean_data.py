import pandas as pd

df = pd.read_csv("./data/vgsales.csv")

# 1. 先清掉 Year = N/A
df = df[df["Year"].notna()]

# 2. 分層抽樣：每個 Genre 抽 2 筆，不夠就取全部
sampled = (
    df.groupby("Genre", group_keys=False)
      .apply(lambda x: x.sample(min(len(x), 2), random_state=42))
)

# 3. 如果抽出來不足 30，再補一些非 Nintendo 的中位銷售遊戲
if len(sampled) < 30:
    remaining = 30 - len(sampled)
    filler = df[~df["Publisher"].str.contains("Nintendo")].sample(remaining, random_state=42)
    sampled = pd.concat([sampled, filler])

# 4. 最後只保留 30 筆
final_30 = sampled.sample(30, random_state=42)

final_30.to_csv("clean_30_rows.csv", index=False)
print("完成！輸出 clean_30_rows.csv")
