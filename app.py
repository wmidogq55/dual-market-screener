import streamlit as st
import pandas as pd
import numpy as np
from FinMind.data import DataLoader
from datetime import datetime, timedelta
import ta

# === 登入 FinMind ===
st.sidebar.title("🔐 FinMind 登入")
user_id = st.sidebar.text_input("帳號", value="", key="user")
password = st.sidebar.text_input("密碼", value="", type="password", key="password")
start_date_input = st.sidebar.date_input("資料起始日", datetime(2023, 4, 6))

if st.sidebar.button("🚀 執行策略選股 + 回測"):
    with st.spinner("登入中..."):
        api = DataLoader()
        try:
            api.login(user_id=user_id, password=password)
            st.success("登入成功")
        except:
            st.error("登入失敗，請檢查帳號密碼")
            st.stop()

    # === 股票清單取得（加上錯誤處理）===
    @st.cache_data(show_spinner=False)
    def get_stock_list():
        try:
            return api.taiwan_stock_info()
        except Exception as e:
            st.error("❌ 無法取得股票清單，可能是 API 配額已用完，請稍後再試。\n\n錯誤訊息：" + str(e))
            st.stop()

    stock_list = get_stock_list()
    stock_ids = stock_list["stock_id"].unique().tolist()

    # === 回測 ===
    result_data = []
    success = 0
    progress = st.progress(0)

    def run_backtest(stock_id):
        try:
            df = api.taiwan_stock_daily(
                stock_id=stock_id,
                start_date=start_date_input.strftime("%Y-%m-%d"),
                end_date=datetime.today().strftime("%Y-%m-%d")
            )
            df["MA20"] = df["close"].rolling(20).mean()
            df["RSI"] = ta.momentum.RSIIndicator(close=df["close"]).rsi()
            df["Signal"] = (df["close"] > df["MA20"]) & (df["RSI"] > 50)

            buy_signals = df[df["Signal"]]
            total_trades = len(buy_signals)
            win_trades = 0

            for i, row in buy_signals.iterrows():
                entry_price = row["close"]
                future_data = df[df.index > i].head(15)
                if not future_data.empty:
                    max_return = (future_data["close"].max() - entry_price) / entry_price
                    if max_return > 0.1:
                        win_trades += 1

            win_rate = win_trades / total_trades if total_trades > 0 else 0
            return {
                "stock_id": stock_id,
                "total_trades": total_trades,
                "win_trades": win_trades,
                "win_rate": win_rate,
                "annualized_return": win_rate * total_trades / 2  # 粗略估算
            }
        except:
            return None

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
