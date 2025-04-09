import streamlit as st
import pandas as pd
import datetime
from FinMind.data import DataLoader
from ta.momentum import RSIIndicator
from ta.trend import MACD, SMAIndicator

# --- 快取 API 登入與股票清單 ---
@st.cache_data(ttl=3600)
def login_and_fetch_info():
    api = DataLoader()
    api.login(user_id="wmidogq55", password="single0829")
    stock_info = api.taiwan_stock_info()
    etf_keywords = "ETF|基金|元大|富邦|群益|國泰|中信|兆豐|永豐|第一金|統一|凱基"
    stock_info = stock_info[
    (stock_info["stock_id"].str.len() == 4) &  # 股票代號長度為4
    (stock_info["type"].isin(["tw", "tpex"])) &  # 只保留上市、上櫃
    ~stock_info["stock_name"].str.contains(etf_keywords)
]


def get_price_data(api, stock_id):
    df = api.taiwan_stock_daily(
        stock_id=stock_id,
        start_date=(datetime.date.today() - datetime.timedelta(days=365)).isoformat(),
        end_date=datetime.date.today().isoformat()
    )
    return df


# --- 條件選單 UI ---
st.set_page_config(page_title="進階條件選股", layout="wide")
st.title("📈 全台股進階策略選股系統")
st.markdown("### 📌 選擇篩選條件")

col1, col2, col3 = st.columns(3)
with col1:
    cond_rsi = st.checkbox("RSI < 30")
    cond_macd = st.checkbox("MACD 黃金交叉")
    cond_break_ma = st.checkbox("突破 20MA")
with col2:
    cond_vol = st.checkbox("成交量放大")
    cond_price60 = st.checkbox("股價 < 60 元")
    cond_foreign = st.checkbox("法人連3日買超")
with col3:
    cond_win = st.checkbox("歷史勝率 > 0.8", value=True)
    cond_return = st.checkbox("平均報酬 > 5%", value=True)

if "stop_flag" not in st.session_state:
    st.session_state.stop_flag = False

run_button = st.button("🚀 開始選股")
stop_button = st.button("⛔ 停止掃描")

if stop_button:
    st.session_state.stop_flag = True

if run_button:
    st.session_state.stop_flag = False
    
    api, stock_info = login_and_fetch_info()
    stock_info = stock_info[~stock_info["stock_name"].str.contains(etf_keywords)]  # ← 這行也可直接放在函式內
    stock_ids = stock_info["stock_id"].tolist()[:300]
    results = []
    progress = st.progress(0)
    status = st.empty()

    for i, stock_id in enumerate(stock_ids):
    if st.session_state.stop_flag:  # ✅ 每次都檢查
        st.warning("⚠️ 掃描已手動中止")
        break
        try:
            print(f"開始分析：{stock_id}")
            status.text(f"正在分析第 {i+1} 檔：{stock_id}")
            progress.progress((i + 1) / len(stock_ids))
        
            df = get_price_data(api, stock_id)
            if df.empty or len(df) < 60:
                continue
        except Exception as e:
            print(f"{stock_id} 資料錯誤：{e}")
            continue

        df["close"] = df["close"].astype(float)
        df["close"] = df["close"].fillna(method="ffill") 
        df["close"] = df["close"].fillna(method="bfill") 
        df["RSI"] = RSIIndicator(df["close"]).rsi()
        macd = MACD(df["close"])
        df["MACD_diff"] = macd.macd_diff()
        df["MACD_cross"] = (df["MACD_diff"].shift(1) < 0) & (df["MACD_diff"] > 0)
        df["SMA20"] = df["close"].rolling(window=20).mean()
        df["vol_mean5"] = df["Trading_Volume"].rolling(5).mean()
        df["vol_up"] = df["Trading_Volume"] > df["vol_mean5"]

        # 今日條件
        today = df.iloc[-1]
        pass_cond = True
        if cond_rsi and today["RSI"] >= 30:
            pass_cond = False
        if cond_macd and not today["MACD_cross"]:
            pass_cond = False
        if cond_break_ma and today["close"] < today["SMA20"]:
            pass_cond = False
        if cond_vol and not today["vol_up"]:
            pass_cond = False
        if cond_price60 and today["close"] >= 60:
            pass_cond = False

        if not pass_cond:
            continue

        # 回測勝率條件（固定用 RSI<30 + 突破20MA）
        signals = df[(df["RSI"] < 30) & (df["close"] > df["SMA20"])]
        if len(signals) == 0:
            continue
        signals["future_return"] = [
            (df.iloc[i+15]["close"] - row["close"]) / row["close"]
            if i + 15 < len(df) else 0
            for i, row in signals.iterrows()
        ]
        signals["win"] = signals["future_return"] > 0.05
        win_rate = signals["win"].mean()
        avg_return = signals["future_return"].mean() * 100

        if cond_win and win_rate < 0.8:
            continue
        if cond_return and avg_return < 5:
            continue

        results.append({
            "股票代號": stock_id,
            "勝率": round(win_rate, 2),
            "平均報酬": round(avg_return, 2)
        })

        progress.progress((i + 1) / len(stock_ids))
        status.text(f"正在分析第 {i + 1} 檔：{stock_id}")

    progress.empty()
    if results:
        df_result = pd.DataFrame(results).sort_values("平均報酬", ascending=False)
        st.success(f"✅ 完成，共找到 {len(df_result)} 檔個股")
        st.dataframe(df_result)
    else:
        st.warning("今天沒有符合條件的進場個股。")
