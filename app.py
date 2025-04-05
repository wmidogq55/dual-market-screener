import streamlit as st
import pandas as pd
import numpy as np
from FinMind.data import DataLoader
import ta
from datetime import datetime, timedelta

# === 使用者登入 ===
api = DataLoader()
api.login(token="eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJkYXRlIjoiMjAyNS0wNC0wNSAyMTozMTo1NyIsInVzZXJfaWQiOiJ3bWlkb2dxNTUiLCJpcCI6IjExMS4yNDYuODIuMjE1In0.EMBmMMyYExvSqI1le-2DCTmOudEhrzBRqqfz_ArAucg")

# === 日期設定 ===
end_date = datetime.today()
start_date = end_date - timedelta(days=120)

# === Streamlit UI ===
st.set_page_config(page_title="全台股即時策略選股系統", layout="wide")
st.title("📈 全台股即時策略選股系統（法人連買 + RSI + 突破 20MA）")

# === 功能說明 ===
with st.expander("📘 策略條件說明"):
    st.markdown("""
    **策略條件：**
    - ✅ 外資連續買超 3 天，且買超總張數符合門檻（小型 300 張、中型 500 張、大型 800 張）
    - ✅ RSI 指標上穿 50
    - ✅ 收盤價突破 20 日均線（視為布林中軸）
    """)

# === 法人連買檢查 ===
def check_legal_buy(df, stock_cap):
    df = df.sort_values("date")
    df["連買張數"] = df["buy"].rolling(window=3).sum()
    if stock_cap < 50e8:
        return df["連買張數"].iloc[-1] >= 300
    elif stock_cap < 300e8:
        return df["連買張數"].iloc[-1] >= 500
    else:
        return df["連買張數"].iloc[-1] >= 800

# === RSI 上穿 50 檢查 ===
def check_rsi_up(df):
    rsi = ta.momentum.RSIIndicator(close=df["close"]).rsi()
    return rsi.iloc[-2] < 50 and rsi.iloc[-1] >= 50

# === 收盤價突破 MA20 ===
def check_price_break_ma(df):
    ma20 = df["close"].rolling(window=20).mean()
    return df["close"].iloc[-1] > ma20.iloc[-1]

# === 核心回測函式 ===
def check_stock(stock_id, market_value):
    try:
        price_df = api.taiwan_stock_price(
            stock_id=stock_id,
            start_date=start_date.strftime("%Y-%m-%d"),
            end_date=end_date.strftime("%Y-%m-%d")
        )
        legal_df = api.taiwan_stock_institutional_investors(
            stock_id=stock_id,
            start_date=start_date.strftime("%Y-%m-%d"),
            end_date=end_date.strftime("%Y-%m-%d")
        )
        if price_df.empty or legal_df.empty:
            return None

        foreign = legal_df[legal_df["name"] == "Foreign_Investor"]
        foreign_group = foreign.groupby("date")["buy"].sum().reset_index()
        df = price_df[["date", "close"]].merge(foreign_group, on="date", how="left").fillna(0)

        if check_legal_buy(df, market_value) and check_rsi_up(df) and check_price_break_ma(df):
            return stock_id
    except:
        return None

# === 抓股票清單 ===
st.info("正在抓取股票清單 ...")
info = api.taiwan_stock_info()
info = info[info["type"] == "s"]  # 只取上市
info = info[["stock_id", "stock_name", "market_value"]]
stock_list = info["stock_id"].tolist()

# === 開始選股 ===
st.success("開始篩選符合策略條件的股票，請稍候 ...")
results = []

for i, row in info.iterrows():
    sid = row["stock_id"]
    mv = row["market_value"]
    res = check_stock(sid, mv)
    if res:
        results.append({
            "股票代碼": row["stock_id"],
            "股票名稱": row["stock_name"],
        })

# === 顯示結果 ===
if results:
    df_result = pd.DataFrame(results)
    st.dataframe(df_result)
    st.download_button("下載結果 CSV", df_result.to_csv(index=False), file_name="策略選股結果.csv")
else:
    st.warning("❌ 沒有符合策略條件的股票")
