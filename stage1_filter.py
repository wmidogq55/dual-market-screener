# stage1_filter.py
import pandas as pd
from ta.momentum import RSIIndicator

def get_watchlist(stock_list, get_price_data, get_institution_data):
    watchlist = []

    for stock_id in stock_list:
        try:
            df = get_price_data(stock_id)
            if df.empty or len(df) < 60:
                continue

            df["RSI"] = RSIIndicator(df["close"]).rsi()
            df["SMA60"] = df["close"].rolling(window=60).mean()
            today = df.iloc[-1]
            cond_rsi = today["RSI"] < 30
            cond_price = today["close"] < today["SMA60"]

            legal = get_institution_data(stock_id)
            legal3 = legal.tail(3)
            cond_foreign = legal3["three_investors_net"].sum() > 0

            cond_count = sum([cond_rsi, cond_price, cond_foreign])
            if cond_count >= 2:
                watchlist.append({
                    "股票代號": stock_id,
                    "符合條件": f"{cond_count}/3",
                    "RSI < 30": cond_rsi,
                    "低於季線": cond_price,
                    "法人連買3日": cond_foreign
                })

        except Exception as e:
            print(f"{stock_id} 錯誤：{e}")
            continue

    return pd.DataFrame(watchlist)