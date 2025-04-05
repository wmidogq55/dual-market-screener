import streamlit as st
import pandas as pd
import numpy as np
from FinMind.data import DataLoader
from datetime import datetime, timedelta
import ta

# === 使用者登入 ===
api = DataLoader()
user_id = st.text_input("帳號", value="", key="wmidogq55")
password = st.text_input("密碼", value="", type="password", key="single0829")
start_date_input = st.text_input("資料起始日", value="2023/04/06")

if st.button("🚀 執行策略選股 + 回測"):
    with st.spinner("登入中..."):
        try:
            api.login(user_id=user_id, password=password)
            st.success("登入成功")
        except Exception as e:
            st.error("登入失敗，請檢查帳號密碼")
            st.stop()

    @st.cache_data(show_spinner=False)
    def get_stock_list():
        try:
            stock_info = api.taiwan_stock_info()
            exclude_keywords = ["ETF", "ETN", "富邦", "元大", "國泰", "中信", "街口", "永豐"]
            stock_info = stock_info[
                (~stock_info["stock_name"].str.contains("|".join(exclude_keywords)))
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
                start_date=start_date_input.replace("/", "-"),
                end_date=datetime.today().strftime("%Y-%m-%d"),
            )
            if len(df) < 60:
                return None

            df["MA20"] = df["close"].rolling(window=20).mean()
            df["RSI"] = ta.momentum.RSIIndicator(df["close"]).rsi()
            df["K"] = ta.momentum.StochRSIIndicator(df["close"]).stochrsi_k()
            df["D"] = ta.momentum.StochRSIIndicator(df["close"]).stochrsi_d()

            win_trades, total_trades = 0, 0
            for i in range(1, len(df)):
                if (
                    df["RSI"].iloc[i] > 50
                    and df["close"].iloc[i] > df["MA20"].iloc[i]
                    and df["K"].iloc[i - 1] < df["D"].iloc[i - 1]
                    and df["K"].iloc[i] > df["D"].iloc[i]
                ):
                    total_trades += 1
                    if df["close"].iloc[i + 5] > df["close"].iloc[i]:  # 模擬持有 5 天
                        win_trades += 1

            win_rate = win_trades / total_trades if total_trades else 0
            return {
                "stock_id": stock_id,
                "total_trades": total_trades,
                "win_trades": win_trades,
                "win_rate": round(win_rate, 4),
                "annualized_return": round(win_rate * 100, 1)
            }
        except:
            return None

    st.subheader("📈 正在執行回測中...")
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
        label="💾 下載回測結果 CSV",
        data=df_result.to_csv(index=False),
        file_name="backtest_result.csv",
        mime="text/csv"
    )
