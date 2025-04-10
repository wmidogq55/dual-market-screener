import streamlit as st
import pandas as pd
import datetime
from FinMind.data import DataLoader
from ta.momentum import RSIIndicator
from ta.trend import MACD

st.set_page_config(page_title="歷史回測系統", layout="wide")
st.title("📊 歷史策略回測系統 v1")

# === API 登入 ===
@st.cache_data(ttl=3600)
def login_api():
    api = DataLoader()
    api.login(user_id="wmidogq55", password="single0829")
    return api

api = login_api()

# === 參數設定 ===
stock_id = st.text_input("輸入股票代號（如 2303）", "2303")
use_rsi = st.checkbox("RSI < 30", value=True)
use_macd = st.checkbox("MACD 黃金交叉", value=True)
hold_days = st.slider("持有天數", 5, 30, 15)
take_profit = st.slider("停利門檻（%）", 1, 20, 5)

start_date = (datetime.date.today() - datetime.timedelta(days=365*2)).isoformat()
end_date = datetime.date.today().isoformat()

# === 回測主函式 ===
def backtest_strategy(df, hold_days, take_profit, use_rsi=True, use_macd=True):
    df["RSI"] = RSIIndicator(df["close"]).rsi()
    macd = MACD(df["close"])
    df["MACD_diff"] = macd.macd_diff()
    df["MACD_cross"] = (df["MACD_diff"].shift(1) < 0) & (df["MACD_diff"] > 0)

    trade_log = []

    for i in range(len(df) - hold_days - 1):
        today = df.iloc[i]
        if use_rsi and today["RSI"] >= 30:
            continue
        if use_macd and not today["MACD_cross"]:
            continue

        entry_price = today["close"]
        entry_date = today["date"]

        future = df.iloc[i+1:i+1+hold_days]
        if future.empty:
            continue

        final_price = future.iloc[-1]["close"]
        max_drawdown = ((future["close"].min() - entry_price) / entry_price) * 100
        return_pct = ((final_price - entry_price) / entry_price) * 100

        win_day = hold_days
        for j, p in enumerate(future["close"]):
            if (p - entry_price) / entry_price >= take_profit / 100:
                win_day = j + 1
                break

        trade_log.append({
            "進場日": entry_date,
            "進場價": round(entry_price, 2),
            "出場日": future.iloc[-1]["date"],
            "出場價": round(final_price, 2),
            "總報酬%": round(return_pct, 2),
            "最大回檔%": round(max_drawdown, 2),
            "持有天數": win_day,
            "是否達標": return_pct >= take_profit
        })

    return pd.DataFrame(trade_log)

# === 資料下載並執行回測 ===
if st.button("🚀 開始回測"):
    st.info("正在下載資料與執行回測...")
    df = api.taiwan_stock_daily(stock_id=stock_id, start_date=start_date, end_date=end_date)
    if df.empty:
        st.error("查無資料")
    else:
        df = df.sort_values("date").reset_index(drop=True)
        df["close"] = df["close"].astype(float)
        trade_log = backtest_strategy(df, hold_days, take_profit, use_rsi, use_macd)

        if trade_log.empty:
            st.warning("❌ 無任何符合進場訊號的紀錄")
        else:
            wins = trade_log["是否達標"].sum()
            win_rate = wins / len(trade_log)
            avg_return = trade_log["總報酬%"].mean()
            max_dd = trade_log["最大回檔%"].min()

            st.success(f"✅ 回測完成！共 {len(trade_log)} 筆交易，勝率 {win_rate:.2%}，平均報酬 {avg_return:.2f}%")
            st.dataframe(trade_log)
