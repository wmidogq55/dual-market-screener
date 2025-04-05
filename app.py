import streamlit as st
import pandas as pd
import numpy as np
from FinMind.data import DataLoader
from datetime import datetime, timedelta
import ta

# === 使用者登入 ===
api = DataLoader()
user = st.sidebar.text_input("帳號", value="wmidogq55")
password = st.sidebar.text_input("密碼", value="single0829", type="password")
start_date = st.sidebar.text_input("資料起始日", value="2023/04/06")

if st.sidebar.button("🚀 執行策略選股 + 回測"):
    with st.spinner("登入中..."):
        try:
            api.login(user_id=user, password=password)
            st.success("登入成功")
        except:
            st.error("登入失敗，請檢查帳號密碼")
            st.stop()

    # === 股票清單取得與篩選 ===
    @st.cache_data(show_spinner=False)
    def get_stock_list():
        try:
            stock_info = api.taiwan_stock_info()
            # 保留上市與上櫃
            stock_info = stock_info[stock_info["industry_category"].isin(["上市", "上櫃"])]
            # 排除 ETF 與常見關鍵字
            exclude_keywords = ["反1", "槓桿", "正2", "ETF", "原油", "美元"]
            stock_info = stock_info[
                (~stock_info["stock_id"].str.startswith("00")) &
                (~stock_info["stock_name"].str.contains("|".join(exclude_keywords)))
            ]
            return stock_info
        except Exception as e:
            st.error("❌ 無法取得股票清單，可能是 API 配額已用完，請稍後再試。

錯誤訊息：" + str(e))
            st.stop()

    stock_list = get_stock_list()
    stock_ids = stock_list["stock_id"].unique().tolist()

    # === 回測邏輯 ===
    @st.cache_data(show_spinner=False)
    def run_backtest(stock_id):
        try:
            df = api.taiwan_stock_daily(
                stock_id=stock_id,
                start_date=datetime.strptime(start_date, "%Y/%m/%d").strftime("%Y-%m-%d"),
                end_date=datetime.today().strftime("%Y-%m-%d"),
            )
            df["date"] = pd.to_datetime(df["date"])
            df = df.set_index("date")
            df["close"] = pd.to_numeric(df["close"])

            # 技術指標
            df["RSI"] = ta.momentum.RSIIndicator(close=df["close"]).rsi()
            df["K"] = ta.momentum.stoch(df["high"], df["low"], df["close"]).stoch()
            df["D"] = ta.momentum.stoch_signal(df["high"], df["low"], df["close"]).stoch_signal()
            df["MA20"] = df["close"].rolling(20).mean()

            signal = (df["RSI"] > 50) & (df["close"] > df["MA20"])
            df["signal"] = signal

            win, total = 0, 0
            for i in range(1, len(df)-10):
                if df["signal"].iloc[i] and not df["signal"].iloc[i-1]:
                    entry_price = df["close"].iloc[i+1]
                    for j in range(i+2, min(i+10, len(df))):
                        if df["close"].iloc[j] > entry_price * 1.1:
                            win += 1
                            break
                    total += 1

            if total == 0:
                return None

            return {
                "stock_id": stock_id,
                "total_trades": total,
                "win_trades": win,
                "win_rate": win / total,
                "annualized_return": round((win / total) * 130, 1),  # 粗略換算年報酬
            }

        except:
            return None

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
