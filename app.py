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
st.title("📈 全台股即時策略選股 + 回測系統")

with st.sidebar:
    st.header("🔐 FinMind 登入")
    user = st.text_input("帳號", value="wmidogq55")
    password = st.text_input("密碼", value="single0829", type="password")
    date_input = st.date_input("資料起始日", value=start_date)
    run_button = st.button("🚀 執行策略選股 + 回測")

@st.cache_data(show_spinner=False)
def get_stock_list():
    try:
        stock_info = api.taiwan_stock_info()
        stock_info = stock_info[stock_info["type"].isin(["twse", "otc"])]
        exclude_keywords = ["ETF", "ETN", "債", "期", "指數", "反1", "2X"]
        stock_info = stock_info[
            ~stock_info["stock_name"].str.contains("|".join(exclude_keywords))
        ]
        return stock_info
    except Exception as e:
        st.error("❌ 無法取得股票清單，可能是 API 配額已用完，請稍後再試。

錯誤訊息：" + str(e))
        st.stop()

stock_list = get_stock_list()
stock_ids = stock_list["stock_id"].unique().tolist()

result = []

def run_backtest(stock_id):
    try:
        df = api.taiwan_stock_daily(
            stock_id=stock_id,
            start_date=start_date.strftime("%Y-%m-%d"),
            end_date=datetime.today().strftime("%Y-%m-%d")
        )
        df = pd.DataFrame(df)
        if len(df) < 60:
            return None
        df["date"] = pd.to_datetime(df["date"])
        df.set_index("date", inplace=True)
        df.sort_index(inplace=True)

        df["k"] = ta.momentum.stoch(df["max"], df["min"], df["close"]).stoch()
        df["d"] = ta.momentum.stoch_signal(df["max"], df["min"], df["close"]).stoch_signal()
        df["rsi"] = ta.momentum.RSIIndicator(df["close"]).rsi()
        df["ma20"] = df["close"].rolling(window=20).mean()

        # 範例策略：KD黃金交叉 + RSI < 30 + 突破均線
        df["signal"] = (df["k"] > df["d"]) & (df["rsi"] < 30) & (df["close"] > df["ma20"])
        df["return"] = df["close"].pct_change()
        df["strategy"] = df["signal"].shift(1) * df["return"]
        df.dropna(inplace=True)

        total_trades = df["signal"].sum()
        win_trades = (df["strategy"] > 0).sum()
        win_rate = win_trades / total_trades if total_trades else 0
        annualized_return = (1 + df["strategy"].mean()) ** 252 - 1

        return {
            "stock_id": stock_id,
            "total_trades": int(total_trades),
            "win_trades": int(win_trades),
            "win_rate": round(win_rate, 4),
            "annualized_return": round(annualized_return * 100, 2)
        }
    except:
        return None

if run_button:
    st.subheader("📊 正在執行回測中...")
    progress = st.progress(0)
    result_data = []
    success = 0

    for i, stock_id in enumerate(stock_ids[:300]):
        res = run_backtest(stock_id)
        if res:
            result_data.append(res)
            success += 1
        progress.progress((i + 1) / 300)

    st.success(f"✅ 完成回測，共有 {success} 檔成功回測")
    df_result = pd.DataFrame(result_data)
    df_result = df_result.sort_values("annualized_return", ascending=False)
    st.dataframe(df_result)

    st.download_button(
        label="📥 下載回測結果 CSV",
        data=df_result.to_csv(index=False),
        file_name="backtest_result.csv",
        mime="text/csv"
    )
