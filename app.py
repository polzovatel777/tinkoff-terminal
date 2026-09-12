import streamlit as st
import urllib.request
import json
import ssl
import pandas as pd
import numpy as np
import plotly.express as px
from datetime import datetime, timedelta
from streamlit_autorefresh import st_autorefresh

ssl._create_default_https_context = ssl._create_unverified_context

st.set_page_config(page_title="Institutional Trading Terminal [Clean Alpha]", page_icon="⚡", layout="wide")

try:
    PUBLIC_TOKEN = st.secrets["PUBLIC_TOKEN"]
except Exception:
    PUBLIC_TOKEN = ""

API_BASE_URL = "https://invest-public-api.tinkoff.ru/rest"

st.title("⚡ Institutional Trading Terminal [Clean Alpha Engine]")
st.markdown("Чистый боевой терминал с прямым шлюзом к биржевым данным Т-Банка.")

# Сайдбар управления
st.sidebar.markdown("### ⚙️ Параметры системы")
min_confidence = st.sidebar.slider("Мин. порог уверенности (Score %)", 50, 85, 60)
auto_refresh_sec = st.sidebar.slider("Частота обновления (сек)", 10, 60, 20)

st.success("🟢 **Шлюз активен:** Потоковое получение реальных рыночных данных.")

if not PUBLIC_TOKEN:
    st.error("⚠️ Ошибка конфигурации: Токен API не обнаружен в secrets!")
else:
    st_autorefresh(interval=auto_refresh_sec * 1000, key="datarefresh")

    # Официальные инструменты с точными FIGI
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

    def fetch_market_data(api_token, base_url, figi_list):
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

    def fetch_candles(api_token, base_url, figi, interval_str="CANDLE_INTERVAL_2_HOURS", days=10):
        url = f"{base_url}/tinkoff.public.invest.api.contract.v1.MarketDataService/GetCandles"
        now = datetime.utcnow()
        past = now - timedelta(days=days)
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
                        dt = datetime.strptime(t_str[:19], "%Y-%m-%dT%H:%M:%S") + timedelta(hours=3)
                        times.append(dt.strftime("%d.%m %H:%M"))
                    
                    hi = int(c.get("high", {}).get("units", 0)) + int(c.get("high", {}).get("nano", 0)) / 1e9
                    lo = int(c.get("low", {}).get("units", 0)) + int(c.get("low", {}).get("nano", 0)) / 1e9
                    cl = int(c.get("close", {}).get("units", 0)) + int(c.get("close", {}).get("nano", 0)) / 1e9
                    vol = float(c.get("volume", 0))

                    if cl > 0:
                        highs.append(hi)
                        lows.append(lo)
                        closes.append(cl)
                        volumes.append(vol)
        except Exception:
            pass
        return times, highs, lows, closes, volumes

    def compute_indicators(closes, highs, lows, volumes):
        if len(closes) < 5:
            return 50.0, 0.0, 0.0, 0.0, 1.0, True
        
        df = pd.DataFrame({'price': closes})
        delta = df['price'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = float((100 - (100 / (1 + rs))).iloc[-1])
        rsi = 50.0 if pd.isna(rsi) else rsi

        exp12 = df['price'].ewm(span=12, adjust=False).mean()
        exp26 = df['price'].ewm(span=26, adjust=False).mean()
        macd_val = float((exp12 - exp26).iloc[-1])
        signal_val = float((exp12 - exp26).ewm(span=9, adjust=False).mean().iloc[-1])
        hist_val = macd_val - signal_val

        cdf = pd.DataFrame({'high': highs, 'low': lows, 'close': closes})
        tr1 = cdf['high'] - cdf['low']
        tr2 = abs(cdf['high'] - cdf['close'].shift(1))
        tr3 = abs(cdf['low'] - cdf['close'].shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = float(tr.rolling(window=14).mean().iloc[-1])
        atr = closes[-1] * 0.01 if pd.isna(atr) or atr == 0 else atr

        vol_ok = True
        if len(volumes) >= 10:
            avg_v = pd.Series(volumes).rolling(window=10).mean().iloc[-1]
            vol_ok = volumes[-1] >= (avg_v * 0.7)

        return rsi, macd_val, signal_val, hist_val, atr, vol_ok

    def evaluate_score(closes, rsi, macd, signal, hist, vol_ok):
        if not closes:
            return 50, "Ожидание"
        
        score = 50
        trend_up = closes[-1] >= closes[0]
        
        if trend_up: score += 20
        else: score -= 20

        if rsi <= 45: score += 25
        elif rsi >= 55: score -= 25

        if hist > 0 and macd > signal: score += 25
        elif hist < 0 and macd < signal: score -= 25

        if vol_ok: score += 10
        else: score -= 10

        final_score = max(5, min(95, score))
        return final_score, trend_up

    live_prices = fetch_market_data(PUBLIC_TOKEN, API_BASE_URL, [i["figi"] for i in all_instruments])

    tab_stocks, tab_futures, tab_scanner = st.tabs(["📈 Акции РФ (Top-10)", "⚡ Фьючерсы (Top-10)", "📊 Сводный сканер"])

    def render_grid(instruments):
        for start in range(0, len(instruments), 3):
            cols = st.columns(3)
            batch = instruments[start:start+3]
            for idx, inst in enumerate(batch):
                figi = inst["figi"]
                times, highs, lows, closes, volumes = fetch_candles(PUBLIC_TOKEN, API_BASE_URL, figi, "CANDLE_INTERVAL_2_HOURS", 15)
                
                current_price = live_prices.get(figi, (closes[-1] if closes else 0.0))
                if current_price == 0.0:
                    with cols[idx]:
                        st.markdown(f"#### {inst['name']}")
                        st.text(f"Тикер: {inst['ticker']}")
                        st.warning("⚠️ Нет котировок в стакане.")
                        st.markdown("---")
                    continue

                if not closes:
                    closes = [current_price]
                    highs = [current_price * 1.002]
                    lows = [current_price * 0.998]
                    volumes = [100.0]

                start_p = closes[0]
                pct_change = ((current_price - start_p) / start_p) * 100 if start_p > 0 else 0.0

                rsi, macd, signal, hist, atr, vol_ok = compute_indicators(closes, highs, lows, volumes)
                score, trend_up = evaluate_score(closes, rsi, macd, signal, hist, vol_ok)

                with cols[idx]:
                    st.markdown(f"#### {inst['name']}")
                    st.text(f"Тикер: {inst['ticker']}")
                    
                    st.metric(
                        label="Цена сделки", 
                        value=f"{current_price:,.2f} {inst['unit']}", 
                        delta=f"{pct_change:+.2f}%"
                    )

                    if score >= min_confidence:
                        st.success(f"🟢 BUY (LONG) | Score: {score}%\nRSI: {rsi:.1f}")
                        sl = current_price - (1.5 * atr)
                        tp = current_price + (3.5 * atr)
                    elif score <= (100 - min_confidence):
                        st.error(f"🔴 SHORT | Score: {score}%\nRSI: {rsi:.1f}")
                        sl = current_price + (1.5 * atr)
                        tp = current_price - (3.5 * atr)
                    else:
                        st.warning(f"🟡 HOLD | Score: {score}%\nRSI: {rsi:.1f}")
                        sl, tp = 0, 0

                    if sl > 0:
                        st.caption(f"🎯 **TP:** `{tp:,.2f}` | 🛡️ **SL:** `{sl:,.2f}`")

                    df_plot = pd.DataFrame({"Время": times if times else ["Сейчас"], "Цена": closes})
                    fig = px.line(df_plot, x="Время", y="Цена", template="plotly_dark")
                    fig.update_layout(margin=dict(l=5, r=5, t=5, b=5), height=130, xaxis=dict(showgrid=False), yaxis=dict(showgrid=True))
                    fig.update_traces(line=dict(color="#00FFA3", width=2))
                    st.plotly_chart(fig, use_container_width=True)
                    st.markdown("---")

    with tab_stocks:
        st.markdown("### Акции РФ — Прямой поток:")
        render_grid(stocks_instruments)

    with tab_futures:
        st.markdown("### Фьючерсы — Прямой поток:")
        render_grid(futures_instruments)

    with tab_scanner:
        st.markdown("### Сводная таблица сканирования рынка:")
        scan_results = []
        for inst in all_instruments:
            _, hi, lo, cl, vol = fetch_candles(PUBLIC_TOKEN, API_BASE_URL, inst["figi"], "CANDLE_INTERVAL_2_HOURS", 15)
            cp = live_prices.get(inst["figi"], (cl[-1] if cl else 0.0))
            if cp == 0.0:
                continue
            rsi, macd, signal, hist, atr, vol_ok = compute_indicators(cl, hi, lo, vol)
            score, _ = evaluate_score(cl, rsi, macd, signal, hist, vol_ok)

            status = "🚀 LONG" if score >= min_confidence else ("📉 SHORT" if score <= (100 - min_confidence) else "⏳ NEUTRAL")
            scan_results.append({
                "Инструмент": inst["name"],
                "Тикер": inst["ticker"],
                "Цена": f"{cp:,.2f} {inst['unit']}",
                "RSI": round(rsi, 1),
                "Score": f"{score}%",
                "Сигнал": status
            })

        if scan_results:
            st.dataframe(pd.DataFrame(scan_results), use_container_width=True, hide_index=True)
        else:
            st.warning("Сбор данных сканера...")

    st.caption(f"⏳ Синхронизация: {(datetime.utcnow() + timedelta(hours=3)).strftime('%d.%m.%Y %H:%M:%S')} МСК")
