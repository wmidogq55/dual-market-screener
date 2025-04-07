import streamlit as st
import pandas as pd
import time
import os
import json
from FinMind.data import DataLoader
from datetime import datetime, timedelta

# 快取檔案設定
CACHE_FILE = "stock_cache.json"
MAX_STOCKS = 300  # 最多處理 300 檔

# 初始化 API
api = DataLoader()
api.login(user_id="wmidogq55", password="single0829")  # 使用帳號密碼登入

@st.cache_data(ttl=3600)
def load_stock_list():
    try:
        stock_info = api.taiwan_stock_info()
        stock_info = stock_info[stock_info["stock_id"].str.len() == 4]  # 排除 ETF
        return stock_info["stock_id"].unique().tolist()
    except Exception as e:
        st.error(f"❌ 無法取得股票清單，錯誤訊息：{e}")
        return []

def get_cached_data():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r") as f:
            return json.load(f)
    return {}

def save_cache(data):
    with open(CACHE_FILE, "w") as f:
        json.dump(data, f)

def fetch_stock_data(stock_id, start_date):
    try:
        df = api.taiwan_stock_daily(
            stock_id=stock_id,
            start_date=start_date,
        )
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").reset_index(drop=True)
        df["20MA"] = df["close"].rolling(20).mean()
        df["RSI"] = compute_rsi(df["close"])
        return df
    except Exception as e:
        return None

def compute_rsi(series, period=14):
    delta = series.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def backtest_strategy(df):
    buy_signals = (df["RSI"] < 30) & (df["close"] > df["20MA"])
    df["buy_signal"] = buy_signals.shift(1)

    returns = []
    for i in range(1, len(df)):
        if df["buy_signal"].iloc[i]:
            buy_price = df["close"].iloc[i]
            future_prices = df["close"].iloc[i + 1:i + 16]
            if not future_prices.empty:
                max_return = (future_prices.max() - buy_price) / buy_price
                returns.append(max_return)
    win_rate = sum([1 for r in returns if r > 0.1]) / len(returns) if returns else 0
    return round(win_rate, 2), round((sum(returns) / len(returns)) * 100, 2) if returns else 0

# ===== Streamlit APP 主體 =====

st.title("📈 全台股即時策略選股（RSI < 30 + 突破 20MA）")

stock_ids = load_stock_list()[:MAX_STOCKS]
cache = get_cached_data()
today = datetime.today().strftime("%Y-%m-%d")
start_date = (datetime.today() - timedelta(days=365)).strftime("%Y-%m-%d")

results = []
progress = st.progress(0)

for i, stock_id in enumerate(stock_ids):
    progress.progress(i / len(stock_ids))

    if stock_id in cache and cache[stock_id]["date"] == today:
        win_rate = cache[stock_id]["win_rate"]
        avg_return = cache[stock_id]["avg_return"]
    else:
        df = fetch_stock_data(stock_id, start_date)
        if df is None or df.empty:
            continue
        win_rate, avg_return = backtest_strategy(df)
        cache[stock_id] = {
            "date": today,
            "win_rate": win_rate,
            "avg_return": avg_return,
        }

    results.append({
        "stock_id": stock_id,
        "win_rate": win_rate,
        "avg_return": avg_return,
    })

save_cache(cache)

df_result = pd.DataFrame(results)
df_result = df_result.sort_values("win_rate", ascending=False)
st.success(f"✅ 完成分析，共分析 {len(df_result)} 檔個股")
st.dataframe(df_result)
