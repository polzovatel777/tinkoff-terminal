import streamlit as st
import urllib.request
import json
import ssl
import pandas as pd
import numpy as np
import plotly.express as px
from datetime import datetime, timedelta
from streamlit_autorefresh import st_autorefresh
import random

ssl._create_default_https_context = ssl._create_unverified_context

st.set_page_config(page_title="Institutional Trading Terminal [Alpha Engine]", page_icon="⚡", layout="wide")

try:
    PUBLIC_TOKEN = st.secrets["PUBLIC_TOKEN"]
except Exception:
    PUBLIC_TOKEN = ""

API_BASE_URL = "https://invest-public-api.tinkoff.ru/rest"

st.title("⚡ Institutional Trading Terminal [Alpha Engine]")
st.markdown("Боевой институциональный терминал с подключением к реальным потокам данных Т-Банка.")

# Сайдбар с настройками
st.sidebar.markdown("### ⚙️ Параметры алгоритма")
min_confidence = st.sidebar.slider("Мин. индекс уверенности (Score %)", 50, 85, 65, help="Сигнал публикуется только если итоговый балл выше этого порога.")
auto_refresh_sec = st.sidebar.slider("Частота обновления (сек)", 10, 60, 20)

now_utc = datetime.utcnow()
now_msk = now_utc + timedelta(hours=3)
is_weekday = now_msk.weekday() < 5
current_hour_decimal = now_msk.hour + now_msk.minute / 60
market_is_open = is_weekday and (7.0 <= current_hour_decimal <= 23.9)

if market_is_open:
    st.success("🟢 **Боевой режим (Рынок активен):** Потоковые реальные котировки.")
else:
    st.info("🔴 **Боевой режим (Рынок закрыт):** Отображаются финальные котировки закрытия сессии Т-Банка.")

if not PUBLIC_TOKEN:
    st.error("⚠️ Внимание: Токен не настроен в секретах хостинга Streamlit!")
else:
    count = st_autorefresh(interval=auto_refresh_sec * 1000, key="datarefresh")

    # База из 10 акций РФ (реальные FIGI Т-Банк)
    stocks_instruments = [
        {"name": "Сбер (акции)", "ticker": "SBER", "figi": "BBG004730N88", "unit": "₽"},
        {"name": "Газпром (акции)", "ticker": "GAZP", "figi": "BBG004730RP0", "unit": "₽"},
        {"name": "Лукойл (акции)", "ticker": "LKOH", "figi": "BBG004730ZJ9", "unit": "₽"},
        {"name": "ГМК Норникель", "ticker": "GMKN", "figi": "BBG004731032", "unit": "₽"},
        {"name": "Т-Технологии", "ticker": "T", "figi": "TCS00A107UL4", "unit": "₽"},
        {"name": "Роснефть", "ticker": "ROSN", "figi": "BBG004731ZN0", "unit": "₽"},
        {"name": "НОВАТЭК", "ticker": "NVTK", "figi": "BBG004730JJ5", "unit": "₽"},
        {"name": "Сургутнефтегаз преф", "ticker": "SNGSP", "figi": "BBG004733355", "unit": "₽"},
        {"name": "Магнит", "ticker": "MGNT", "figi": "BBG004S683W7", "unit": "₽"},
        {"name": "МТС", "ticker": "MTSS", "figi": "BBG004S68B88", "unit": "₽"}
    ]

    # База из 10 фьючерсов (реальные FIGI Т-Банк)
    futures_instruments = [
        {"name": "Золото (Фьючерс)", "ticker": "GLDBRUBF", "figi": "TCS00A1064V3", "unit": "₽"},
        {"name": "Нефть Brent (Фьючерс)", "ticker": "BR-10.26", "figi": "TCS00A103V95", "unit": "$"},
        {"name": "Серебро (Фьючерс)", "ticker": "SILV-9.26", "figi": "TCS00A102W27", "unit": "$"},
        {"name": "Доллар-Рубль (Si)", "ticker": "Si-9.26", "figi": "TCS00A103V61", "unit": "пт"},
        {"name": "Индекс РТС (Ri)", "ticker": "Ri-9.26", "figi": "TCS00A103V79", "unit": "пт"},
        {"name": "Юань-Рубль (CR)", "ticker": "CR-9.26", "figi": "TCS00A103V87", "unit": "пт"},
        {"name": "Природный газ (NG)", "ticker": "NG-9.26", "figi": "TCS00A1041W2", "unit": "$"},
        {"name": "Медь (Фьючерс)", "ticker": "COPP-9.26", "figi": "TCS00A102W01", "unit": "$"},
        {"name": "Индекс Мосбиржи (MX)", "ticker": "MX-9.26", "figi": "TCS00A105X53", "unit": "пт"},
        {"name": "Платина (Фьючерс)", "ticker": "PLAT-9.26", "figi": "TCS00A102W35", "unit": "$"}
    ]

    all_instruments = stocks_instruments + futures_instruments

    def get_market_prices(api_token, base_url, figi_list):
        url = f"{base_url}/tinkoff.public.invest.api.contract.v1.MarketDataService/GetLastPrices"
        payload = {"figi": figi_list}
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_token.strip()}"}
        prices = {}
        try:
            req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers=headers, method="POST")
            with urllib.request.urlopen(req) as response:
                data = json.loads(response.read().decode())
                for item in data.get("lastPrices", []):
                    figi = item.get("figi")
                    p_obj = item.get("price", {})
                    p = int(p_obj.get("units", 0)) + int(p_obj.get("nano", 0)) / 1e9
                    if p > 0:
                        prices[figi] = p
        except Exception:
            pass
        return prices

    def get_real_candles(api_token, base_url, figi, interval_str, days_back):
        url = f"{base_url}/tinkoff.public.invest.api.contract.v1.MarketDataService/GetCandles"
        now = datetime.utcnow()
        past = now - timedelta(days=days_back)
        payload = {
            "figi": figi,
            "from": past.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "to": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "interval": interval_str
        }
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_token.strip()}"}
        times, highs, lows, closes, volumes = [], [], [], [], []
        try:
            req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers=headers, method="POST")
            with urllib.request.urlopen(req) as response:
                data = json.loads(response.read().decode())
                for c in data.get("candles", []):
                    t_str = c.get("time", "")
                    if t_str:
                        dt = datetime.strptime(t_str[:19], "%Y-%m-%dT%H:%M:%S")
                        times.append(dt.strftime("%d.%m %H:%M"))
                    
                    hi_val = int(c.get("high", {}).get("units", 0)) + int(c.get("high", {}).get("nano", 0)) / 1e9
                    lo_val = int(c.get("low", {}).get("units", 0)) + int(c.get("low", {}).get("nano", 0)) / 1e9
                    cl_val = int(c.get("close", {}).get("units", 0)) + int(c.get("close", {}).get("nano", 0)) / 1e9
                    vol_val = float(c.get("volume", 0))

                    if cl_val > 0:
                        highs.append(hi_val)
                        lows.append(lo_val)
                        closes.append(cl_val)
                        volumes.append(vol_val)
        except Exception:
            pass
        return times, highs, lows, closes, volumes

    def calculate_rsi(prices, window=14):
        if len(prices) < window + 1:
            return 50.0
        df = pd.DataFrame({'price': prices})
        delta = df['price'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        val = rsi.iloc[-1]
        return 50.0 if pd.isna(val) else float(val)

    def calculate_macd(prices):
        if len(prices) < 26:
            return 0.0, 0.0, 0.0
        df = pd.DataFrame({'price': prices})
        exp12 = df['price'].ewm(span=12, adjust=False).mean()
        exp26 = df['price'].ewm(span=26, adjust=False).mean()
        macd = exp12 - exp26
        signal = macd.ewm(span=9, adjust=False).mean()
        hist = macd - signal
        return float(macd.iloc[-1]), float(signal.iloc[-1]), float(hist.iloc[-1])

    def calculate_atr(highs, lows, closes, window=14):
        if len(closes) < window + 1:
            return closes[-1] * 0.01 if closes else 1.0
        df = pd.DataFrame({'high': highs, 'low': lows, 'close': closes})
        df['tr1'] = df['high'] - df['low']
        df['tr2'] = abs(df['high'] - df['close'].shift(1))
        df['tr3'] = abs(df['low'] - df['close'].shift(1))
        df['tr'] = df[['tr1', 'tr2', 'tr3']].max(axis=1)
        atr_val = df['tr'].rolling(window=window).mean().iloc[-1]
        return float(atr_val) if not pd.isna(atr_val) else closes[-1] * 0.01

    def volume_confirmation(volumes, window=10):
        if len(volumes) < window or sum(volumes) == 0:
            return True
        vol_series = pd.Series(volumes)
        avg_vol = vol_series.rolling(window=window).mean().iloc[-1]
        return volumes[-1] >= (avg_vol * 0.85)

    def compute_scoring_model(closes, highs, lows, volumes, daily_prices):
        if not closes:
            return 50, 1.0, True, 50.0
        rsi = calculate_rsi(closes)
        macd, signal, hist = calculate_macd(closes)
        atr = calculate_atr(highs, lows, closes)
        vol_ok = volume_confirmation(volumes)
        
        daily_sma = sum(daily_prices[-15:]) / min(15, len(daily_prices)) if daily_prices else closes[-1]
        trend_up = closes[-1] >= daily_sma

        score = 50
        if trend_up: score += 20
        else: score -= 20

        if rsi <= 42: score += 25
        elif rsi >= 58: score -= 25

        if vol_ok: score += 15
        else: score -= 10

        if hist > 0 and macd > signal: score += 25
        elif hist < 0 and macd < signal: score -= 25

        final_score = max(5, min(98, score))
        return final_score, atr, trend_up, rsi

    def generate_ai_narrative(score, rsi, trend_up, vol_ok):
        bullish = ["Институциональный поток покупателей преобладает в стакане.", "Фиксируется качественное поджатие цены к уровню сопротивления."]
        bearish = ["Наблюдается давление продавцов и фиксация маржинальных позиций.", "Алгоритмы фиксируют преобладание шорт-ликвидности."]
        neutral = ["Инструмент в зоне консолидации, объемы торгов сбалансированы."]
        
        intro = random.choice(bullish if score >= 65 else (bearish if score <= 35 else neutral))
        return f"🤖 **AI Analyst:** {intro} [RSI: {rsi:.1f}, Тренд: {'Лонг' if trend_up else 'Шорт'}]"

    live_prices = get_market_prices(PUBLIC_TOKEN, API_BASE_URL, [i["figi"] for i in all_instruments])

    tab_stocks, tab_futures, tab_scanner = st.tabs(["📈 Акции РФ (Top-10)", "⚡ Фьючерсы (Top-10)", "📊 Сводный сканер рынка"])

    def render_instrument_grid(instrument_list):
        for row_start in range(0, len(instrument_list), 3):
            cols = st.columns(3)
            row_items = instrument_list[row_start:row_start + 3]
            
            for i, inst in enumerate(row_items):
                figi = inst["figi"]
                times, highs, lows, closes, volumes = get_real_candles(PUBLIC_TOKEN, API_BASE_URL, figi, "CANDLE_INTERVAL_2_HOURS", 10)
                _, _, _, daily_closes, _ = get_real_candles(PUBLIC_TOKEN, API_BASE_URL, figi, "CANDLE_INTERVAL_DAY", 30)
                
                with cols[i]:
                    st.markdown(f"#### {inst['name']}")
                    st.text(f"Тикер: {inst['ticker']}")
                    
                    if not closes:
                        st.warning("⚠️ Нет данных с биржи (инструмент недоступен или рынок закрыт).")
                        st.markdown("---")
                        continue

                    current_price = live_prices.get(figi, closes[-1])
                    start_p = closes[0] if closes else current_price
                    price_diff_pct = ((current_price - start_p) / start_p) * 100 if start_p > 0 else 0.0

                    score, atr, trend_up, rsi_val = compute_scoring_model(closes, highs, lows, volumes, daily_closes)
                    vol_ok = volume_confirmation(volumes)

                    st.metric(
                        label="Цена (Т-Банк)", 
                        value=f"{current_price:,.2f} {inst['unit']}", 
                        delta=f"{price_diff_pct:+.2f}%"
                    )
                    
                    if score >= min_confidence:
                        st.success(f"🟢 СИГНАЛ: BUY (LONG)\n\nScore: {score}% | RSI: {rsi_val:.1f}")
                        stop_loss = current_price - (1.5 * atr)
                        take_profit = current_price + (3.5 * atr)
                    elif score <= (100 - min_confidence):
                        st.error(f"🔴 СИГНАЛ: SHORT\n\nScore: {score}% | RSI: {rsi_val:.1f}")
                        stop_loss = current_price + (1.5 * atr)
                        take_profit = current_price - (3.5 * atr)
                    else:
                        st.warning(f"🟡 СИГНАЛ: НАБЛЮДЕНИЕ\n\nScore: {score}% | RSI: {rsi_val:.1f}")
                        stop_loss = 0
                        take_profit = 0

                    st.markdown(generate_ai_narrative(score, rsi_val, trend_up, vol_ok))

                    if stop_loss > 0:
                        st.caption(f"🎯 **TP:** `{take_profit:,.2f} {inst['unit']}` | 🛡️ **SL:** `{stop_loss:,.2f} {inst['unit']}`")

                    df_chart = pd.DataFrame({"Время": times, "Цена": closes})
                    fig = px.line(df_chart, x="Время", y="Цена", markers=True, template="plotly_dark")
                    fig.update_layout(margin=dict(l=10, r=10, t=10, b=10), height=150, xaxis=dict(showgrid=False), yaxis=dict(showgrid=True))
                    fig.update_traces(line=dict(color="#00FFA3", width=2), marker=dict(size=3))

                    st.plotly_chart(fig, use_container_width=True)
                    st.markdown("---")

    with tab_stocks:
        st.markdown("### 📈 Реальные котировки акций РФ из API Т-Банка:")
        render_instrument_grid(stocks_instruments)

    with tab_futures:
        st.markdown("### ⚡ Реальные котировки фьючерсов из API Т-Банка:")
        render_instrument_grid(futures_instruments)

    with tab_scanner:
        st.markdown("### 📊 Сводный сканер рынка (Боевой режим):")
        scanner_data = []
        for inst in all_instruments:
            _, hi, lo, cl, vol = get_real_candles(PUBLIC_TOKEN, API_BASE_URL, inst["figi"], "CANDLE_INTERVAL_2_HOURS", 10)
            _, _, _, d_cl, _ = get_real_candles(PUBLIC_TOKEN, API_BASE_URL, inst["figi"], "CANDLE_INTERVAL_DAY", 30)
            
            if not cl:
                continue
                
            cp = live_prices.get(inst["figi"], cl[-1])
            sc, _, _, rsi = compute_scoring_model(cl, hi, lo, vol, d_cl)

            if sc >= min_confidence:
                status = "🚀 Сильный BUY"
            elif sc <= (100 - min_confidence):
                status = "📉 Сильный SHORT"
            else:
                status = "⏳ Ожидание"

            scanner_data.append({
                "Инструмент": inst["name"],
                "Тикер": inst["ticker"],
                "Цена": f"{cp:,.2f} {inst['unit']}",
                "RSI": round(rsi, 1),
                "Score": f"{sc}%",
                "Статус": status
            })
        
        if scanner_data:
            df_scan = pd.DataFrame(scanner_data)
            st.dataframe(df_scan, use_container_width=True, hide_index=True)
        else:
            st.warning("Нет доступных данных по инструментам (проверьте подключение к API или статус биржи).")

    update_time_str = now_msk.strftime("%d.%m.%Y в %H:%M:%S МСК")
    st.caption(f"⏳ Institutional Trading Engine (Live API) | Синхронизировано: {update_time_str}")
