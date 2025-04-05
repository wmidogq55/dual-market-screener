import streamlit as st
import pandas as pd
from FinMind.data import DataLoader
import datetime
import ta

# === 使用者登入 ===
api = DataLoader()
api.login(user_id="你的帳號", password="你的密碼")  # 請替成你的 FinMind 帳號資料

# === 參數設定 ===
start_date = "2023-01-01"
end_date = "2024-12-31"

# === Streamlit UI ===
st.title("📈 全臺股即時策略選股系統")

# 輸入要算的股票代碼列表
stock_list_input = st.text_area("請輸入股票代碼列表（用、分隔）", "2454，6176，3481，3037，3006")
stock_list = [s.strip() for s in stock_list_input.split("\uff0c") if s.strip()]

# === 策略回測函數 ===
def backtest(stock_id):
    try:
        price_df = api.taiwan_stock_daily(stock_id=stock_id, start_date=start_date, end_date=end_date)
        legal_df = api.taiwan_stock_institutional_investors(stock_id=stock_id, start_date=start_date, end_date=end_date)
        if price_df.empty or legal_df.empty:
            return None

        df = price_df[['date', 'close']].copy()
        df['date'] = pd.to_datetime(df['date'])
        df['rsi'] = ta.momentum.RSIIndicator(close=df['close']).rsi()
        df['ma20'] = df['close'].rolling(window=20).mean()

        legal = legal_df[legal_df['name'] == 'Foreign_Investor']
        legal = legal.groupby('date')['buy'].sum().reset_index()
        legal.columns = ['date', 'foreign_buy']
        df = pd.merge(df, legal, on='date', how='left')
        df['foreign_buy'] = df['foreign_buy'].fillna(0)

        # === 進場條件 ===
        df['entry_signal'] = (
            (df['foreign_buy'].rolling(window=3).sum() > 0) &
            (df['rsi'] > 50) &
            (df['close'] > df['ma20'])
        )

        entry_dates = df[df['entry_signal']].index.tolist()

        total_profit = 0
        win_count = 0
        entry_count = 0

        for entry_idx in entry_dates:
            if entry_idx + 30 >= len(df):
                continue
            entry_price = df.loc[entry_idx, 'close']
            future_prices = df.loc[entry_idx+1:entry_idx+30, 'close']
            max_profit = (future_prices.max() - entry_price) / entry_price
            min_drawdown = (future_prices.min() - entry_price) / entry_price

            if min_drawdown < -0.1:
                continue  # 停損

            entry_count += 1
            profit = (future_prices.iloc[-1] - entry_price)
            total_profit += profit
            if profit > 0:
                win_count += 1

        if entry_count == 0:
            return None

        return {
            '股票代碼': stock_id,
            '進場次數': entry_count,
            '總投入': entry_count * 200000,
            '總獲利': round(total_profit * 5),  # 五倍檔款
            '總報酬率': round((total_profit * 5) / (entry_count * 200000) * 100, 2),
            '勝率': round((win_count / entry_count) * 100, 2)
        }
    except:
        return None

# === 跟擊執行 ===
if st.button("開始策略篩選"):
    with st.spinner("正在請求資料與回測..."):
        results = []
        for stock_id in stock_list:
            result = backtest(stock_id)
            if result:
                results.append(result)
        if results:
            df_result = pd.DataFrame(results)
            df_result = df_result.sort_values(by='總報酬率', ascending=False).reset_index(drop=True)
            st.success(f"篩選完成，有 {len(df_result)} 個標的符合條件")
            st.dataframe(df_result)
            csv = df_result.to_csv(index=False).encode('utf-8-sig')
            st.download_button(label="📄 下載 CSV", data=csv, file_name="strategy_selection.csv", mime='text/csv')
        else:
            st.warning("沒有標的符合條件")
