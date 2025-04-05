import streamlit as st
import pandas as pd
import numpy as np
from FinMind.data import DataLoader
from datetime import datetime, timedelta
import ta

# === 使用者登入 ===
api = DataLoader()
api.login(user_id="wmidogq55", password="single0829")

# === 日期設定 ===
end_date = datetime.today()
start_date = end_date - timedelta(days=120)

# === Streamlit UI ===
st.set_page_config(page_title="全台股即時策略選股系統", layout="wide")
st.title("📈 全台股即時策略選股系統（法人連買 + RSI + 突破 20MA）")

with st.expander("🧠 策略條件說明："):
    st.markdown("""
**策略條件：**
✅ 外資連續買超 3 天，且買超總張數符合門檻（小型股 300 張、中型股 500 張、大型股 800 張）  
✅ RSI 上穿 50  
✅ 收盤價突破 20MA
""")

# === 函數：判斷外資連買且買超數量達標 ===
def check_legal_buy(df, stock_cap):
    df = df.sort_values("date")
    buy_volume = df["buy"].rolling(window=3).sum()
    if stock_cap < 50:  # 小型股
        return buy_volume.iloc[-1] >= 300
    elif stock_cap < 300:  # 中型股
        return buy_volume.iloc[-1] >= 500
    else:  # 大型股
        return buy_volume.iloc[-1] >= 800

# === 函數：判斷 RSI 上穿 50 且收盤突破 20MA ===
def check_rsi_price(df):
    df = df.sort_values("date")
    df["rsi"] = ta.momentum.RSIIndicator(df["close"]).rsi()
    df["ma20"] = df["close"].rolling(window=20).mean()
    
    rsi_cross = df["rsi"].iloc[-2] < 50 and df["rsi"].iloc[-1] >= 50
    price_break = df["close"].iloc[-1] > df["ma20"].iloc[-1]
    
    return rsi_cross and price_break

# === 主流程：掃描所有上市股票 ===
st.info("📡 篩選中，請稍候...")

all_stocks = api.taiwan_stock_info()
listed_stocks = all_stocks[all_stocks["type"] == "twse"]
result = []

for stock_id in listed_stocks["stock_id"]:
    try:
        price_df = api.taiwan_stock_daily(stock_id=stock_id, start_date=start_date.strftime('%Y-%m-%d'))
        legal_df = api.taiwan_stock_institutional_investors(stock_id=stock_id, start_date=start_date.strftime('%Y-%m-%d'))
        if price_df.empty or legal_df.empty:
            continue

        legal_df = legal_df[legal_df["name"] == "Foreign_Investor"][["date", "buy"]]

        stock_cap = listed_stocks[listed_stocks["stock_id"] == stock_id]["market_value"].values[0] / 1e8  # 單位轉換成億元

        if check_legal_buy(legal_df, stock_cap) and check_rsi_price(price_df):
            result.append(stock_id)
    except Exception as e:
        continue

# === 顯示結果 ===
if result:
    st.success("✅ 符合條件的股票：")
    st.write("、".join(result))
else:
    st.warning("❌ 沒有符合條件的股票")
