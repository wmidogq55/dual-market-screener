import pandas as pd
from ta.momentum import RSIIndicator

def get_watchlist(
    stock_list,
    get_price_data,
    get_institution_data,
    use_rsi=True,
    use_kd=True,
    use_foreign=True,
    use_sideways=False,
    use_long_weak=False,
    use_revenue_up=False,
    use_yoy_turn=False
):
    watchlist = []

    for stock_id in stock_list:
        try:
            df = get_price_data(stock_id)
            if df.empty or len(df) < 60:
                continue

            df["close"] = df["close"].astype(float)
            df["RSI"] = RSIIndicator(df["close"]).rsi()
            df["SMA60"] = df["close"].rolling(window=60).mean()

            today = df.iloc[-1]

            # 條件初始化與安全處理
            cond_rsi = today["RSI"] < 30 if use_rsi else True
            cond_price = today["close"] < today["SMA60"] if use_kd else True

            cond_foreign = True
            if use_foreign:
                legal = get_institution_data(stock_id)
                if legal is None or legal.empty:
                    cond_foreign = False
                else:
                    legal3 = legal.tail(3)
                    cond_foreign = legal3["three_investors_net"].sum() > 0

            # 先做簡單三條件：RSI + KD + 法人
            cond_count = sum([cond_rsi, cond_price, cond_foreign])
            required = sum([use_rsi, use_kd, use_foreign])
            if cond_count >= max(1, required // 2):  # 通過一半以上條件就進 watchlist
                watchlist.append({
                    "股票代號": stock_id
                })

        except Exception as e:
            print(f"{stock_id} 發生錯誤：{e}")
            continue

    return pd.DataFrame(watchlist)
