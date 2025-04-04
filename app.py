import pandas as pd
from finmind.data import DataLoader
from ta.momentum import RSIIndicator
from ta.trend import MACD

# 設定 API Token
token = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJkYXRlIjoiMjAyNS0wNC0wMyAxMDo0OTo1MiIsInVzZXJfaWQiOiJ3bWlkb2dxNTUiLCJpcCI6IjExMS4yNDYuODIuMjE1In0.WClrNkfmH8vKQkEIQb6rVmAnQToh4hQeYIAJLlO2siU"

# 登入 FinMind
api = DataLoader()
api.login_by_token(api_token=token)

# 抓台股所有上市股票清單
stock_list = api.taiwan_stock_info()
stock_ids = stock_list["stock_id"].unique().tolist()

# 篩選用：可先試 10 檔測試
test_ids = stock_ids[:10]

results = []

for stock_id in test_ids:
    try:
        df = api.taiwan_stock_daily(
            stock_id=stock_id,
            start_date="2024-03-01",
            end_date="2025-04-03"
        )
        if len(df) < 35:
            continue
        df = df.sort_values("date")
        df["close"] = df["close"].astype(float)

        rsi = RSIIndicator(close=df["close"], window=14)
        df["rsi"] = rsi.rsi()

        macd = MACD(close=df["close"])
        df["macd"] = macd.macd()
        df["macd_signal"] = macd.macd_signal()

        last = df.iloc[-1]
        if last["rsi"] < 30 and last["macd"] > last["macd_signal"]:
            results.append({
                "stock_id": stock_id,
                "rsi": round(last["rsi"], 2),
                "macd": round(last["macd"], 2),
                "macd_signal": round(last["macd_signal"], 2),
            })
    except Exception as e:
        print(f"{stock_id} 發生錯誤：{e}")
        continue

result_df = pd.DataFrame(results)
print(result_df)
result_df.to_excel("rsi_macd_result.xlsx", index=False)
