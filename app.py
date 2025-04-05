import streamlit as st
import pandas as pd
import numpy as np
from FinMind.data import DataLoader
import ta
from datetime import datetime, timedelta

# === 使用者登入 ===
api = DataLoader()
api.login(token="eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJkYXRlIjoiMjAyNS0wNC0wNSAyMTozMTo1NyIsInVzZXJfaWQiOiJ3bWlkb2dxNTUiLCJpcCI6IjExMS4yNDYuODIuMjE1In0.EMBmMMyYExvSqI1le-2DCTmOudEhrzBRqqfz_ArAucg")  # <<== 這裡換成你的 token

# === 日期區間設定 ===
end_date = datetime.today()
start_date = end_date - timedelta(days=120)

# === Streamlit UI ===
st.set_page_config(page_title="📈 全台股即時策略選股系統", layout="wide")
st.title("📈 全台股即時策略選股系統（法人連買 + RSI + 突破 20MA）")

with st.expander("🧠 策略條件說明"):
    st.markdown("""
    **策略條件：**
    ✅ 外資連續買超 3 天，且買超總張數符合門檻（小型股 300 張、中型股 500 張、大型股 800 張）  
    ✅ RSI 上穿 50  
    ✅ 收盤價突破 20MA
    """)

# === 核心函式 ===
def check_legal_buy(df, stock_cap):
    df = df.sort_values("date")
    df["連買張數"] = df["buy"].rolling(window=3).sum()
    if stock_cap < 50e8:
        return df["連買張數"].iloc[-1] >= 300
    elif stock_cap < 300e8:
        return df["連買張數"].iloc[-1] >= 500
    else:
        return df["連買張數"].iloc[-1] >= 800

def calculate_indicators(df):
    df = df.sort_values("date")
    df["RSI"] = ta.momentum.RSIIndicator(close=df["close"], window=14).rsi()
    df["MA20"] = df["close"].rolling(window=20).mean()
    return df

def strategy_filter(stock_id):
    try:
        price_df = api.taiwan_stock_daily(stock_id=stock_id, start_date=start_date.strftime("%Y-%m-%d"), end_date=end_date.strftime("%Y-%m-%d"))
        legal_df = api.taiwan_stock_institutional_investors(stock_id=stock_id, start_date=start_date.strftime("%Y-%m-%d"), end_date=end_date.strftime("%Y-%m-%d"))
        if price_df.empty or legal_df.empty:
            return None

        stock_cap = price_df["Trading_Volume"].iloc[-1] * price_df["close"].iloc[-1]

        # 條件一：法人連買判斷
        legal_buy_pass = check_legal_buy(legal_df, stock_cap)

        # 條件二：技術指標計算
        price_df = calculate_indicators(price_df)
        rsi_pass = price_df["RSI"].iloc[-2] < 50 and price_df["RSI"].iloc[-1] > 50
        ma_break = price_df["close"].iloc[-2] < price_df["MA20"].iloc[-2] and price_df["close"].iloc[-1] > price_df["MA20"].iloc[-1]

        if legal_buy_pass and rsi_pass and ma_break:
            return {
                "股票代碼": stock_id,
                "收盤價": price_df["close"].iloc[-1],
                "RSI": round(price_df["RSI"].iloc[-1], 2),
                "MA20": round(price_df["MA20"].iloc[-1], 2),
            }
    except Exception as e:
        return None

# === 輸入股票代碼 ===
stock_input = st.text_area("輸入股票代碼（用頓號分隔，例如 2454、2303）", "2454、3037、2303、2603")
stock_list = [s.strip() for s in stock_input.split("、") if s.strip()]

# === 執行選股 ===
if st.button("🚀 開始選股"):
    st.write("📊 篩選中，請稍候...")
    results = []
    for stock_id in stock_list:
        result = strategy_filter(stock_id)
        if result:
            results.append(result)

    if results:
        st.success(f"✅ 共找到 {len(results)} 檔符合條件的股票")
        st.dataframe(pd.DataFrame(results))
    else:
        st.warning("❌ 沒有符合條件的股票")
