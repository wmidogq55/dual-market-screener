import streamlit as st
import pandas as pd
import ta
from finmind.data import DataLoader

# 使用者輸入 RSI 門檻
rsi_threshold = st.slider('RSI 門檻值（小於則列入）', min_value=5, max_value=50, value=30, step=1)

# 初始化 FinMind
api = DataLoader()
api.login_by_token(api_token='你的Token')

# 取得台股上市公司列表（範例使用前幾檔）
stock_list = api.taiwan_stock_info()[:5]

results = []

for stock_id in stock_list['stock_id']:
    try:
        df = api.taiwan_stock_daily(
            stock_id=stock_id,
            start_date="2024-01-01",
            end_date="2025-04-04"
        )
        if len(df) < 50:
            continue
        df = df.sort_values("date")
        df.set_index("date", inplace=True)
        df["RSI"] = ta.momentum.RSIIndicator(close=df["close"]).rsi()
        df["MACD"] = ta.trend.MACD(close=df["close"]).macd_diff()

        latest = df.iloc[-1]
        rsi_value = latest["RSI"]
        macd_cross = latest["MACD"] > 0 and df["MACD"].iloc[-2] <= 0

        if rsi_value < rsi_threshold and macd_cross:
            results.append({
                "股票代號": stock_id,
                "RSI": round(rsi_value, 2),
                "MACD黃金交叉": macd_cross
            })

    except Exception as e:
        st.warning(f"{stock_id} 發生錯誤：{e}")

if results:
    df_result = pd.DataFrame(results)
    st.success("✅ 符合條件的標的如下")
    st.dataframe(df_result)
    st.download_button("下載結果 Excel", df_result.to_csv(index=False), "篩選結果.csv")
else:
    st.warning("⚠️ 沒有符合條件的股票。")
