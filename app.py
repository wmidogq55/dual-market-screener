
import streamlit as st
import pandas as pd
import datetime
from FinMind.data import DataLoader
from ta.momentum import RSIIndicator
from ta.trend import SMAIndicator

# 登入帳密方式 + 設定快取
@st.cache_data(ttl=3600)
def login_and_fetch_info():
    api = DataLoader()
    api.login(user_id="wmidogq55", password="single0829")
    try:
        stock_info = api.taiwan_stock_info()
        stock_info = stock_info[stock_info["stock_id"].str.len() == 4]  # 過濾上市櫃個股（排除ETF）
        return api, stock_info["stock_id"].unique().tolist()
    except Exception as e:
        st.error("❌ 無法取得股票清單，請檢查帳密或 API 狀況：\n" + str(e))
        st.stop()

# 取得個股資料並判斷是否符合條件
def analyze_stock(api, stock_id):
    try:
        df = api.taiwan_stock_daily(
            stock_id=stock_id,
            start_date=(datetime.date.today() - datetime.timedelta(days=365)).isoformat(),
            end_date=datetime.date.today().isoformat()
        )
        if df.empty or len(df) < 60:
            return None

        df["close"] = df["close"].astype(float)
        df["rsi"] = RSIIndicator(df["close"], window=14).rsi()
        df["sma20"] = SMAIndicator(df["close"], window=20).sma_indicator()

        # 判斷今天是否 RSI < 30 且 收盤突破20MA
        latest = df.iloc[-1]
        if latest["rsi"] < 30 and latest["close"] > latest["sma20"]:
            # 做回測：當日 RSI < 30 且突破 20MA 後持股15天
            signals = df[(df["rsi"] < 30) & (df["close"] > df["sma20"])].copy()
            if len(signals) == 0:
                return None
            signals["future_return"] = [
                (df.iloc[i+15]["close"] - row["close"]) / row["close"]
                if i + 15 < len(df) else 0
                for i, row in signals.iterrows()
            ]
            signals["win"] = signals["future_return"] > 0.05  # 定義成功為 15 天內漲超過 5%
            win_rate = signals["win"].mean()
            avg_return = signals["future_return"].mean() * 100  # 百分比
            return {"stock_id": stock_id, "win_rate": win_rate, "avg_return": round(avg_return, 2)}
        else:
            return None
    except:
        return None

# 主程式
st.title("📈 全台股即時策略選股（RSI < 30 + 突破 20MA）")
st.caption("僅顯示：今天出現進場訊號 + 背後歷史勝率 > 0.8 的個股")

api, stock_ids = login_and_fetch_info()
stock_ids = stock_ids[:300]  # 防爆處理：最多掃描 300 檔

results = []
progress = st.progress(0)
status = st.empty()

for i, stock_id in enumerate(stock_ids):
    progress.progress((i+1)/len(stock_ids))
    status.text(f"正在分析第 {i+1} 檔：{stock_id}")
    result = analyze_stock(api, stock_id)
    if result and result["win_rate"] >= 0.8:
        results.append(result)

progress.empty()
status.empty()

if results:
    df_result = pd.DataFrame(results).sort_values("avg_return", ascending=False)
    st.success(f"✅ 完成分析，共找到 {len(df_result)} 檔進場訊號個股")
    st.dataframe(df_result)
else:
    st.warning("今天沒有符合條件的進場個股。")
