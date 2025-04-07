
import streamlit as st
import pandas as pd
import datetime
from FinMind.data import DataLoader
from ta.momentum import RSIIndicator
from ta.trend import MACD
import time

# 快取設定 + API 登入
@st.cache_data(ttl=3600)
def get_stock_info():
    api = DataLoader()
    api.login(user_id="wmidogq55", password="single0829")
    stock_info = api.taiwan_stock_info()
    stock_info = stock_info[stock_info["stock_id"].str.len() == 4]
    return stock_info["stock_id"].unique().tolist()

@st.cache_data(ttl=3600)
def get_price_data(stock_id):
    api = DataLoader()
    api.login(user_id="wmidogq55", password="single0829")
    df = api.taiwan_stock_daily(
        stock_id=stock_id,
        start_date=(datetime.datetime.now() - datetime.timedelta(days=365)).strftime('%Y-%m-%d'),
        end_date=datetime.datetime.now().strftime('%Y-%m-%d')
    )
    return df

def check_strategy(stock_id):
    df = get_price_data(stock_id)
    if len(df) < 60:
        return None
    df["MA20"] = df["close"].rolling(window=20).mean()
    df["RSI"] = RSIIndicator(df["close"]).rsi()
    macd = MACD(df["close"])
    df["MACD_diff"] = macd.macd_diff()
    df["MACD_cross"] = (df["MACD_diff"].shift(1) < 0) & (df["MACD_diff"] > 0)

    today = df.iloc[-1]
    prev = df.iloc[-2]

    if today["RSI"] < 30 and today["MACD_cross"] and today["close"] < today["MA20"] * 1.05:
        return stock_id
    return None

st.set_page_config(page_title="台股抄底策略選股", layout="wide")
st.title("📉 台股抄底策略選股（RSI < 30 + MACD黃金交叉 + 接近20MA）")
st.caption("點擊下方按鈕後開始分析，僅顯示今天出現進場訊號的個股。")

run_button = st.button("🚀 執行策略分析")

if run_button:
    stock_list = get_stock_info()
    result = []
    progress = st.progress(0, text="正在分析中...")

    for i, stock_id in enumerate(stock_list[:300]):
        res = check_strategy(stock_id)
        if res:
            result.append(res)
        progress.progress((i + 1) / len(stock_list[:300]))

    st.success(f"✅ 分析完成，共找到 {len(result)} 檔符合條件的個股。")

    if result:
        st.dataframe(pd.DataFrame(result, columns=["符合進場條件個股"]))
    else:
        st.warning("今天沒有符合條件的進場個股。")
