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
            today = df.iloc[-1]  # ⏩ 提早定義

            # RSI
            cond_rsi = True
            if use_rsi:
                df["RSI"] = RSIIndicator(df["close"]).rsi()
                cond_rsi = today["RSI"] < 30

            # KD
            cond_kd = True
            if use_kd:
                low_min = df["low"].rolling(window=9).min()
                high_max = df["high"].rolling(window=9).max()
                df["RSV"] = (df["close"] - low_min) / (high_max - low_min) * 100
                df["K"] = df["RSV"].ewm(com=2).mean()
                df["D"] = df["K"].ewm(com=2).mean()
                cond_kd = (
                    (df["K"].iloc[-1] < 20) and
                    (df["K"].iloc[-2] < df["D"].iloc[-2]) and
                    (df["K"].iloc[-1] > df["D"].iloc[-1])
                )

            # 法人資料
            cond_foreign = True
            if use_foreign:
                legal = get_institution_data(stock_id)
                if legal is None or legal.empty:
                    cond_foreign = False
                else:
                    legal3 = legal.tail(3)
                    cond_foreign = legal3["three_investors_net"].sum() > 0

            # 整體條件判斷
            cond_count = sum([cond_rsi, cond_kd, cond_foreign])
            required = sum([use_rsi, use_kd, use_foreign])

            if cond_count >= required:  # ✅ 改為「條件全滿足才納入」
                watchlist.append({
                    "股票代號": stock_id,
                    "符合 RSI": cond_rsi,
                    "符合 KD 黃金交叉": cond_kd,
                    "法人連3日買超": cond_foreign,
                    "RSI": round(today["RSI"], 2) if use_rsi else None,
                    "K": round(df["K"].iloc[-1], 2) if use_kd else None,
                    "D": round(df["D"].iloc[-1], 2) if use_kd else None,
                    "法人買超合計": legal3["three_investors_net"].sum() if use_foreign else None
                })

        except Exception as e:
            print(f"{stock_id} 發生錯誤：{e}")
            continue

    return pd.DataFrame(watchlist)
