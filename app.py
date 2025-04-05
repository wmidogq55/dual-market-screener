import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from FinMind.data import DataLoader
from ta.momentum import RSIIndicator
from ta.trend import MACD
import time

st.set_page_config(page_title="全台股策略回測 App", layout="wide")
st.title("📈 全台股即時策略 + 回測系統")

# === 使用者登入 ===
st.sidebar.header("🔐 FinMind 登入")
user_id = st.sidebar.text_input("帳號", value="wmidogq55")
password = st.sidebar.text_input("密碼", type="password", value="single0829")
start_date = st.sidebar.date_input("資料起始日", value=datetime.today() - timedelta(days=730))
run_button = st.sidebar.button("🚀 執行策略選股 + 回測")

if run_button:
    st.info("登入中...")
    api = DataLoader()
    try:
        api.login(user_id=user_id, password=password)
        st.success("登入成功")
    except:
        st.error("登入失敗，請檢查帳密")
        st.stop()

    @st.cache_data(show_spinner=False)
    def get_stock_list():
    try:
        return api.taiwan_stock_info()
    except Exception as e:
        st.error("❌ 無法取得股票清單，可能是 API 配額已用完，請稍後再試。\n\n錯誤訊息：" + str(e))
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
            if df.empty or len(df) < 100:
                return None

            df = df.sort_values("date")
            df["rsi"] = RSIIndicator(df["close"]).rsi()
            macd = MACD(df["close"])
            df["macd"] = macd.macd()
            df["macd_signal"] = macd.macd_signal()
            df["ma20"] = df["close"].rolling(20).mean()

            trades = []
            in_position = False
            entry_price = 0

            for i in range(1, len(df)):
                row = df.iloc[i]
                prev = df.iloc[i - 1]

                if not in_position:
                    if row["rsi"] < 30 and row["macd"] > row["macd_signal"] and row["close"] > row["ma20"]:
                        entry_price = row["close"]
                        in_position = True
                else:
                    gain = (row["close"] - entry_price) / entry_price
                    if gain >= 0.1 or gain <= -0.05 or (prev["rsi"] >= 70 and row["rsi"] < prev["rsi"]):
                        trades.append(gain)
                        in_position = False

            if trades:
                win_rate = sum(1 for r in trades if r > 0) / len(trades)
                avg_return = sum(trades) / len(trades)
                return {
                    "stock_id": stock_id,
                    "trades": len(trades),
                    "win_rate": round(win_rate, 2),
                    "avg_return": round(avg_return, 4),
                    "annualized_return": round(avg_return * len(trades), 4)
                }
        except:
            return None

    st.subheader("📊 正在執行回測中...")
    progress = st.progress(0)
    result_data = []
    success = 0

    for i, stock_id in enumerate(stock_ids[:300]):  # 限制 300 檔防止爆流量
        res = run_backtest(stock_id)
        if res:
            result_data.append(res)
            success += 1
        progress.progress((i+1)/300)
        time.sleep(0.2)  # 控制速率避免 API 超限

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
