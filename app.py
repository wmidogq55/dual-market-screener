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

with st.expander("💡 策略條件說明："):
    st.markdown("""
**策略條件：**
✅ 外資連續買超 3 天，且買超總張數符合門檻（小型股 300 張、中型股 500 張、大型股 800 張）  
✅ RSI 上穿 50  
✅ 收盤價突破 20MA
""")

@st.cache_data(show_spinner=False)
def get_stock_list():
    try:
        stock_info = api.taiwan_stock_info()
        exclude_keywords = ["ETF", "指數", "反1", "期貨", "債", "外幣", "原油", "黃金", "正2"]
        stock_info = stock_info[
            (stock_info["type"].isin(["twse", "otc"])) &
            (~stock_info["stock_name"].str.contains("|".join(exclude_keywords)))
        ]
        return stock_info
    except Exception as e:
        st.error("❌ 無法取得股票清單，可能是 API 配額已用完，請稍後再試。\n\n錯誤訊息：" + str(e))
        st.stop()

def run_backtest(stock_id):
    try:
        df = api.taiwan_stock_daily(
            stock_id=stock_id,
            start_date=start_date.strftime("%Y-%m-%d"),
            end_date=end_date.strftime("%Y-%m-%d")
        )
        if df.empty:
            return None
        df["k"] = ta.momentum.stoch(df["close"], df["low"], df["high"], window=9, smooth_window=3)
        df["d"] = df["k"].rolling(window=3).mean()
        df["rsi"] = ta.momentum.rsi(df["close"], window=14)
        df["ma20"] = df["close"].rolling(window=20).mean()
        df["signal"] = (df["rsi"] > 50) & (df["close"] > df["ma20"])
        df["position"] = df["signal"].shift(1).fillna(False)
        df["return"] = df["close"].pct_change()
        df["strategy"] = df["position"] * df["return"]
        total_trades = df["position"].sum()
        win_trades = ((df["position"] == True) & (df["return"] > 0)).sum()
        win_rate = win_trades / total_trades if total_trades > 0 else 0
        ann_return = df["strategy"].mean() * 252
        return {
            "stock_id": stock_id,
            "total_trades": int(total_trades),
            "win_trades": int(win_trades),
            "win_rate": round(win_rate, 4),
            "annualized_return": round(ann_return * 100, 1)
        }
    except Exception:
        return None

st.subheader("⏳ 正在執行回測中...")
progress = st.progress(0)
result_data = []
success = 0

stock_list = get_stock_list()
stock_ids = stock_list["stock_id"].unique().tolist()

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
