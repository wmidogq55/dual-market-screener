import streamlit as st
import pandas as pd
import finmind
from finmind.data import DataLoader
from datetime import datetime, timedelta
import ta

# 設定 FinMind API token
api = DataLoader()
api.login_by_token(api_token="eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJkYXRlIjoiMjAyNS0wNC0wNSAyMTozMTo1NyIsInVzZXJfaWQiOiJ3bWlkb2dxNTUiLCJpcCI6IjExMS4yNDYuODIuMjE1In0.EMBmMMyYExvSqI1le-2DCTmOudEhrzBRqqfz_ArAucg")

# 篩選條件：只保留上市/上櫃個股，不包含 ETF 或特別股
def get_stock_list():
    try:
        stock_info = api.taiwan_stock_info()
        stock_info = stock_info[
            (stock_info["type"].isin(["twse", "tpex"])) &
            (~stock_info["stock_id"].str.startswith("00")) &
            (~stock_info["stock_name"].str.contains("受益|債|反1|期|2X|永豐"))
        ]
        return stock_info
    except Exception as e:
        st.error("無法取得股票清單，可能是 API 配額用完，請稍後再試。\n\n錯誤訊息: " + str(e))
        st.stop()

# 技術指標篩選
def strategy_rsi_break_ma(df):
    df["rsi"] = ta.momentum.RSIIndicator(df["close"], window=14).rsi()
    df["ma20"] = df["close"].rolling(window=20).mean()
    df["signal"] = (df["rsi"] < 30) & (df["close"] > df["ma20"])
    return df

# 回測模擬策略
def backtest(df):
    df = strategy_rsi_break_ma(df)
    df = df.dropna()
    total_trades = 0
    win_trades = 0
    returns = []

    for i in range(len(df)):
        if df.iloc[i]["signal"]:
            entry_price = df.iloc[i]["close"]
            for j in range(i + 1, min(i + 15, len(df))):
                ret = (df.iloc[j]["close"] - entry_price) / entry_price
                if ret > 0.1:
                    win_trades += 1
                    returns.append(ret)
                    break
            total_trades += 1
    if total_trades == 0:
        return None
    win_rate = win_trades / total_trades
    avg_return = pd.Series(returns).mean() * (252 / 15) if returns else 0
    return {
        "total_trades": total_trades,
        "win_trades": win_trades,
        "win_rate": round(win_rate, 2),
        "annualized_return": round(avg_return * 100, 2)
    }

# 取得資料與執行回測
def run_backtest(stock_id):
    try:
        df = api.taiwan_stock_daily(
            stock_id=stock_id,
            start_date=(datetime.today() - timedelta(days=400)).strftime("%Y-%m-%d"),
            end_date=datetime.today().strftime("%Y-%m-%d"),
        )
        df = df[df["Trading_Volume"] > 0].copy()
        df.rename(columns={"close": "close"}, inplace=True)
        result = backtest(df)
        if result:
            return {
                "stock_id": stock_id,
                **result
            }
    except Exception as e:
        return None

# Streamlit UI
st.set_page_config(layout="wide")
st.title("全台股即時策略選股（RSI+突破20MA）")

stock_list = get_stock_list()
stock_ids = stock_list["stock_id"].unique().tolist()

progress = st.progress(0)
results = []
total = len(stock_ids)

for i, sid in enumerate(stock_ids):
    res = run_backtest(sid)
    if res:
        results.append(res)
    progress.progress((i + 1) / total)

st.success(f"回測完成，成功分析 {len(results)} 檔股票")

if results:
    df_result = pd.DataFrame(results)
    df_result = df_result.sort_values("win_rate", ascending=False)
    st.dataframe(df_result)
    st.download_button("下載回測結果 CSV", df_result.to_csv(index=False), "result.csv", "text/csv")
else:
    st.warning("沒有符合條件的股票。")
