import streamlit as st
import pandas as pd
import random
import datetime
import traceback
from stage1_filter import get_watchlist
from FinMind.data import DataLoader
from ta.momentum import RSIIndicator
from ta.trend import MACD

# --- 快取 API 登入與股票清單 ---
@st.cache_data(ttl=3600)
def login_and_fetch_info():
    api = DataLoader()
    api.login(user_id="wmidogq55", password="single0829")
    stock_info = api.taiwan_stock_info()
    etf_keywords = "ETF|基金|元大|富邦|群益|國泰|中信|兆豐|永豐|第一金|統一|凱基"
    stock_info = stock_info[
        (stock_info["stock_id"].str.len() == 4) &
        (stock_info["type"].isin(["tw", "tpex"])) &
        ~stock_info["stock_name"].str.contains(etf_keywords)
    ]
    return api, stock_info

def get_price_data(api, stock_id):
    st.write(f"正在抓取 {stock_id} 股價資料")
    df = api.taiwan_stock_daily(
        stock_id=stock_id,
        start_date=(datetime.date.today() - datetime.timedelta(days=365)).isoformat(),
        end_date=datetime.date.today().isoformat()
    )
    return df

def get_institution_data(api, stock_id):
    df = api.taiwan_stock_institutional_investors(
        stock_id=stock_id,
        start_date=(datetime.date.today() - datetime.timedelta(days=10)).isoformat(),
        end_date=datetime.date.today().isoformat()
    )
    if df.empty:
        return pd.DataFrame()

    df = df[df["institutional_investor"].isin([
        "Foreign_Investor", "Investment_Trust", "Dealer_Self", "Dealer_Hedging"
    ])]
    pivot = df.pivot_table(
        index="date",
        columns="institutional_investor",
        values="buy_sell",
        aggfunc="sum"
    ).fillna(0)
    pivot["three_investors_net"] = pivot.sum(axis=1)
    return pivot.reset_index()

# --- 回測引擎 ---
def backtest_signals(df, use_rsi=True, use_ma=True, use_macd=True):
    cond = pd.Series([True] * len(df))
    if use_rsi:
        cond &= df["RSI"] < 30
    if use_ma:
        cond &= df["close"] > df["SMA20"]
    if use_macd:
        cond &= df["MACD_cross"]

    signals = df[cond]

    returns = []
    max_drawdowns = []
    win_days = []

    for i, row in signals.iterrows():
        entry_price = row["close"]
        future_prices = df.loc[i+1:i+15]["close"]
        if future_prices.empty:
            continue

        future_return = (future_prices - entry_price) / entry_price
        returns.append(future_return.iloc[-1])
        max_drawdown = (future_prices.min() - entry_price) / entry_price
        max_drawdowns.append(max_drawdown)

        win_day = 15
        for j, ret in enumerate(future_return):
            if ret > 0.05:
                win_day = j + 1
                break
        win_days.append(win_day)

    if len(returns) == 0:
        return 0, 0, 0, 0

    win_rate = sum(r > 0.05 for r in returns) / len(returns)
    avg_return = sum(returns) / len(returns)
    max_dd = min(max_drawdowns)
    avg_days = sum(win_days) / len(win_days)

    print(f"✅ 共回測 {len(signals)} 筆訊號，勝率={win_rate:.2f}, 報酬={avg_return * 100:.2f}%")
    return win_rate, avg_return * 100, max_dd * 100, avg_days
    
if "stage" not in st.session_state:
    st.session_state.stage = "setup"  # 初始狀態為「設定條件」
if "stop_flag" not in st.session_state:
    st.session_state.stop_flag = False
if "has_run" not in st.session_state:
    st.session_state.has_run = False

# --- UI ---
st.set_page_config(page_title="進階條件選股", layout="wide")
st.title("📈 全台股進階策略選股系統")
st.markdown("### 📌 選擇篩選條件")
st.markdown("### 🧪 第一階段觀察條件 (可自選篩選)")

with st.expander("🛠️ 展開設定觀察條件"):
    watch_rsi = st.checkbox("RSI < 30", value=True)
    watch_kd = st.checkbox("月 KD < 20 且黃金交叉", value=True)
    watch_foreign = st.checkbox("法人連買（投信連3～5日買超）", value=True)
    watch_sideways = st.checkbox("股價盤整未突破", value=True)
    watch_long_term_weak = st.checkbox("長期低於季線但近期止穩", value=True)
    watch_revenue_up = st.checkbox("近 2~3 月營收月增率轉正", value=True)
    watch_yoy_turn_positive = st.checkbox("YoY 年增率由負轉正", value=True)

run_button = st.button("🚀 開始選股")
stop_button = st.button("⛔ 停止掃描")

if stop_button:
    st.session_state.stop_flag = True

if run_button:
    st.session_state.stop_flag = False
    st.session_state.has_run = False
    st.session_state.stage = "scan"  # ✅ 這是關鍵

if st.session_state.stage == "scan":  # ✅ 改這行條件，不能用 has_run
    st.session_state.has_run = True   # ✅ 一進來才標記已經執行

    api, stock_info = login_and_fetch_info()
    stock_ids = random.sample(stock_info["stock_id"].tolist(), 300)
    results = []
    progress = st.progress(0)
    status = st.empty()
        
    # 注意這段在 if 裡但不在 with 裡
    watchlist_df = get_watchlist(
        stock_list=stock_ids,
        get_price_data=lambda stock_id: get_price_data(api, stock_id),
        get_institution_data=lambda stock_id: get_institution_data(api, stock_id),
        use_rsi=watch_rsi,
        use_kd=watch_kd,
        use_foreign=watch_foreign,
        use_sideways=watch_sideways,
        use_long_weak=watch_long_term_weak,
        use_revenue_up=watch_revenue_up,
        use_yoy_turn=watch_yoy_turn_positive
    )
    
    st.write("watch_rsi =", watch_rsi)
    st.write("get_watchlist =", get_watchlist)
    st.write(f"觀察清單數量：{len(watchlist_df)}")
    st.subheader("📋 階段一：低基期觀察清單")
    st.dataframe(watchlist_df)

    if watchlist_df.empty:
        st.warning("⚠️ 今日無符合條件的低基期觀察股，請明日再試")
        st.stop()

    st.subheader("🚀 階段二：今日可考慮進場標的")
    col1, col2, col3 = st.columns(3)
    with col1:
        cond_rsi = st.checkbox("RSI < 30", value=False)
        cond_macd = st.checkbox("MACD 黃金交叉", value=False)
        cond_break_ma = st.checkbox("突破 20MA", value=False)
    with col2:
        cond_vol = st.checkbox("成交量放大", value=False)
        cond_price60 = st.checkbox("股價 < 60 元", value=False)
        cond_foreign = st.checkbox("法人連3日買超", value=False)
    with col3:
        cond_win = st.checkbox("歷史勝率 > 0.8", value=True)
        cond_return = st.checkbox("平均報酬 > 5%", value=True)
        
    if not any([cond_rsi, cond_macd, cond_break_ma, cond_vol, cond_price60, cond_foreign]):
        st.warning("⚠️ 請至少勾選一個進場條件")
        st.stop()

    for i, stock_id in enumerate(watchlist_df["股票代號"]):
        try:
            status.text(f"正在抓取 {stock_id} 股價資料")  # ✅ 用 status 顯示，不干擾畫面
            progress.progress((i + 1) / len(watchlist_df))  # ✅ 正常更新進度條
    
            df = get_price_data(api, stock_id)
            if df.empty or len(df) < 60:
                continue
        except Exception as e:
            st.error(f"⚠️ 錯誤：{e}")
            st.text(traceback.format_exc())
            print(f"{stock_id} 資料錯誤：{e}")  # 這個保留給 Console 看
            continue
    
        df["close"] = df["close"].astype(float)
        df["close"] = df["close"].fillna(method="ffill").fillna(method="bfill")
        df["RSI"] = RSIIndicator(df["close"]).rsi()
        macd = MACD(df["close"])
        df["MACD_diff"] = macd.macd_diff()
        df["MACD_cross"] = (df["MACD_diff"].shift(1) < 0) & (df["MACD_diff"] > 0)
        df["SMA20"] = df["close"].rolling(window=20).mean()
        df["vol_mean5"] = df["Trading_Volume"].rolling(5).mean()
        df["vol_up"] = df["Trading_Volume"] > df["vol_mean5"]
    
        if cond_foreign:
            inst_df = None
            try:
                inst_df = get_institution_data(api, stock_id)
                if inst_df is None or inst_df.empty or inst_df["three_investors_net"].tail(3).sum() <= 0:
                    continue
            except Exception as e:
                print(f"{stock_id} 法人資料錯誤：{e}")
                continue
    
        today = df.iloc[-1]
        if cond_rsi and today["RSI"] >= 30: continue
        if cond_macd and not today["MACD_cross"]: continue
        if cond_break_ma and today["close"] < today["SMA20"]: continue
        if cond_vol and not today["vol_up"]: continue
        if cond_price60 and today["close"] >= 60: continue
    
        win_rate, avg_return, max_dd, avg_days = backtest_signals(
            df,
            use_rsi=cond_rsi,
            use_ma=cond_break_ma,
            use_macd=cond_macd
        )
    
        if cond_win and win_rate < 0.8:
            continue
        if cond_return and avg_return < 5:
            continue
    
        results.append({
            "股票代號": stock_id,
            "勝率": round(win_rate, 2),
            "平均報酬": round(avg_return, 2),
            "最大回檔": round(max_dd, 2),
            "平均持有天數": round(avg_days, 1)
        })
    
        if st.session_state.stop_flag:
            progress.empty()
            if results:
                df_result = pd.DataFrame(results).sort_values("平均報酬", ascending=False)
                st.success(f"✅ 掃描已中止，共找到 {len(df_result)} 檔個股")
                st.dataframe(df_result)
            else:
                st.warning("⚠️ 掃描已中止，今天沒有符合條件的進場個股。")
            break
            
    progress.empty()
    if results:
        df_result = pd.DataFrame(results).sort_values("平均報酬", ascending=False)
        st.success(f"✅ 掃描完成，共找到 {len(df_result)} 檔個股")
        st.dataframe(df_result)
    else:
        st.warning("⚠️ 掃描完成，今天沒有符合條件的進場個股。")
