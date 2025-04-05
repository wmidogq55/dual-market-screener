import streamlit as st
import pandas as pd
import numpy as np
from FinMind.data import DataLoader
from datetime import datetime, timedelta
import ta

# === 使用者登入 ===
api = DataLoader()

# Streamlit 登入區塊
st.title("📈 全台股即時策略 + 回測系統")

with st.sidebar:
    st.markdown("## 🔐 FinMind 登入")
    user_id = st.text_input("帳號", value="wmidogq55")
    password = st.text_input("密碼", type="password", value="single0829")
    start_date = st.date_input("資料起始日", value=datetime.today() - timedelta(days=365))
    login_button = st.button("🚀 執行策略選股 + 回測")

if login_button:
    st.info("登入中...")
    api.login(user_id=user_id, password=password)
    st.success("登入成功")

    # 取得股票清單（只保留上市與上櫃，不含 ETF 與特殊字樣）
    @st.cache_data(show_spinner=False)
    def get_stock_list():
        try:
            stock_info = api.taiwan_stock_info()
            exclude_keywords = ["ETF", "反1", "兩倍", "期", "購", "售", "債", "永豐", "元大"]
            stock_info = stock_info[
                (~stock_info["stock_id"].str.startswith("00")) &  # 排除 ETF
                (~stock_info["stock_name"].str.contains("|".join(exclude_keywords)))
            ]
            return stock_info
        except Exception as e:
            st.error("❌ 無法取得股票清單，可能是 API 配額已用完，請稍後再試。

錯誤訊息: " + str(e))
            st.stop()

    stock_list = get_stock_list()
    stock_ids = stock_list["stock_id"].unique().tolist()

    result = []

    # 回測主邏輯
    def run_backtest(stock_id):
        try:
            df = api.taiwan_stock_daily(
                stock_id=stock_id,
                start_date=start_date.strftime("%Y-%m-%d"),
                end_date=datetime.today().strftime("%Y-%m-%d")
            )
            if df is None or df.empty:
                return None

            df["sma20"] = df["close"].rolling(window=20).mean()
            df["rsi"] = ta.momentum.RSIIndicator(df["close"], window=14).rsi()
            df["k"] = ta.momentum.stoch(df["high"], df["low"], df["close"]).stoch()
            df["d"] = ta.momentum.stoch_signal(df["high"], df["low"], df["close"]).stoch_signal()

            # 抄底條件：RSI < 30 且突破 20 日均線
            df["signal"] = (df["rsi"] < 30) & (df["close"] > df["sma20"])
            df["position"] = df["signal"].shift(1).fillna(False)

            df["returns"] = df["close"].pct_change()
            df["strategy"] = df["returns"] * df["position"]
            df.dropna(inplace=True)

            total_trades = int(df["position"].sum())
            win_trades = int((df["strategy"] > 0).sum())
            win_rate = win_trades / total_trades if total_trades > 0 else 0
            annualized_return = np.round(df["strategy"].mean() * 252 * 100, 2)

            return {
                "stock_id": stock_id,
                "total_trades": total_trades,
                "win_trades": win_trades,
                "win_rate": win_rate,
                "annualized_return": annualized_return,
            }
        except:
            return None

    st.subheader("📊 正在執行回測中...")
    progress = st.progress(0)
    result_data = []
    success = 0

    for i, stock_id in enumerate(stock_ids[:300]):
        res = run_backtest(stock_id)
        if res:
            result_data.append(res)
            success += 1
        progress.progress((i+1)/300)
    
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
