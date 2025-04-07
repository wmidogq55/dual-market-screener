
import streamlit as st
import pandas as pd
import datetime
from FinMind.data import DataLoader

# 登入帳密方式 + 設定快取
@st.cache_data(ttl=3600)
def get_stock_list():
    api = DataLoader()
    api.login(user_id="wmidogq55", password="single0829")
    try:
        stock_info = api.taiwan_stock_info()
        stock_info = stock_info[stock_info["stock_id"].str.len() == 4]  # 僅保留上市上櫃個股
        return stock_info
    except Exception as e:
        st.error("❌ 無法取得股票清單，請檢查帳密或 API 狀況\n\n錯誤訊息：" + str(e))
        st.stop()

# 計算技術指標與進場條件
def analyze_stock(stock_id):
    api = DataLoader()
    api.login(user_id="wmidogq55", password="single0829")
    end_date = datetime.date.today()
    start_date = end_date - datetime.timedelta(days=365)

    try:
        df = api.taiwan_stock_daily(stock_id=stock_id, start_date=str(start_date), end_date=str(end_date))
        df = pd.DataFrame(df)
        if df.empty:
            return None
        df["date"] = pd.to_datetime(df["date"])
        df.set_index("date", inplace=True)
        df["ma20"] = df["close"].rolling(window=20).mean()
        df["rsi"] = compute_rsi(df["close"])
        df["macd"], df["macd_signal"] = compute_macd(df["close"])
        df["突破20MA"] = df["close"] > df["ma20"]

        # 找出符合條件的進場點
        df["entry"] = (df["rsi"] < 30) & (df["macd"] > df["macd_signal"]) & (df["突破20MA"])
        trades = []
        for i in range(len(df)-15):
            if df["entry"].iloc[i]:
                entry_price = df["close"].iloc[i]
                future_prices = df["close"].iloc[i+1:i+16]
                ret = (future_prices.max() - entry_price) / entry_price * 100
                trades.append(ret)

        if trades:
            win_trades = [r for r in trades if r >= 10]
            return {
                "stock_id": stock_id,
                "total_trades": len(trades),
                "win_trades": len(win_trades),
                "win_rate": round(len(win_trades)/len(trades), 2),
                "avg_return": round(pd.Series(trades).mean(), 2)
            }
        return None
    except:
        return None

# RSI 計算函式
def compute_rsi(series, period=14):
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

# MACD 計算函式
def compute_macd(series, fast=12, slow=26, signal=9):
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd = ema_fast - ema_slow
    signal_line = macd.ewm(span=signal, adjust=False).mean()
    return macd, signal_line

# 主程式邏輯
st.title("📈 全台股即時策略選股（RSI < 30 + 突破 20MA）")
stock_list = get_stock_list()
stock_ids = stock_list["stock_id"].unique().tolist()

results = []
for stock_id in stock_ids[:300]:  # 每次最多 300 檔
    result = analyze_stock(stock_id)
    if result and result["win_rate"] >= 0.8:
        results.append(result)

if results:
    df_result = pd.DataFrame(results)
    df_result = df_result.sort_values("avg_return", ascending=False)
    st.success(f"✅ 完成分析，共分析 {len(df_result)} 檔個股")
    st.dataframe(df_result)
else:
    st.warning("未找到符合條件的個股。")
