import streamlit as st
import pandas as pd
import numpy as np
from FinMind.data import DataLoader
from datetime import datetime, timedelta
import ta

# 登入 FinMind
api = DataLoader()
api.login(user_id="wmidogq55", password="single0829")

# 時間區間
end_date = datetime.today()
start_date = end_date - timedelta(days=180)

# Streamlit 設定
st.set_page_config(page_title="全台股即時策略選股", layout="wide")
st.title("📈 全台股即時策略選股（RSI+突破20MA）")

# 取得股票清單（排除 ETF）
@st.cache_data(show_spinner=False)
def get_stock_list():
    try:
        stock_info = api.taiwan_stock_info()
        exclude_keywords = ["ETF", "ETN", "指數", "反1", "正2"]
        stock_info = stock_info[
            (stock_info["type"].isin(["twse", "otc"])) &
            (~stock_info["stock_name"].str.contains("|".join(exclude_keywords)))
        ]
        return stock_info
    except Exception as e:
        st.error("❌ 無法取得股票清單，可能是 API 配額已用完，請稍後再試。\n\n錯誤訊息：" + str(e))
        st.stop()

stock_list = get_stock_list()
stock_ids = stock_list["stock_id"].unique().tolist()

# 回測邏輯
def run_backtest(stock_id):
    try:
        df = api.taiwan_stock_daily(
            stock_id=stock_id,
            start_date=start_date.strftime("%Y-%m-%d"),
            end_date=end_date.strftime("%Y-%m-%d")
        )
        if df.empty or len(df) < 50:
            return None

        df["date"] = pd.to_datetime(df["date"])
        df.set_index("date", inplace=True)
        df["rsi"] = ta.momentum.RSIIndicator(df["close"]).rsi()
        df["ma20"] = df["close"].rolling(window=20).mean()
        df["signal"] = (df["rsi"] > 50) & (df["close"] > df["ma20"])
        df["return"] = df["close"].pct_change()
        df["strategy"] = df["signal"].shift(1) * df["return"]

        total_trades = df["signal"].sum()
        win_trades = ((df["strategy"] > 0) & df["signal"].shift(1)).sum()
        win_rate = win_trades / total_trades if total_trades > 0 else 0
        annualized_return = df["strategy"].mean() * 252 if not df["strategy"].isna().all() else 0

        return {
            "stock_id": stock_id,
            "total_trades": int(total_trades),
            "win_trades": int(win_trades),
            "win_rate": round(win_rate, 2),
            "annualized_return": round(annualized_return * 100, 2)
        }
    except:
        return None

# 執行回測
st.subheader("📊 正在執行回測，請稍候...")
progress = st.progress(0)
results = []

for i, stock_id in enumerate(stock_ids[:300]):
    res = run_backtest(stock_id)
    if res:
        results.append(res)
    progress.progress((i + 1) / len(stock_ids[:300]))

if results:
    df_result = pd.DataFrame(results)
    df_result = df_result.sort_values("annualized_return", ascending=False)
    st.success(f"✅ 回測完成，成功分析 {len(df_result)} 檔股票")
    st.dataframe(df_result)

    st.download_button(
        label="💾 下載回測結果 CSV",
        data=df_result.to_csv(index=False),
        file_name="backtest_result.csv",
        mime="text/csv"
    )
else:
    st.warning("⚠ 沒有任何股票符合條件或 API 已限制。")
