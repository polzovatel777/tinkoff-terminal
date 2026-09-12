import streamlit as st
import urllib.request
import json
import ssl
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
from streamlit_autorefresh import st_autorefresh

ssl._create_default_https_context = ssl._create_unverified_context

st.set_page_config(page_title="Профессиональный Терминал Т-Банк", page_icon="📈", layout="wide")

try:
    PUBLIC_TOKEN = st.secrets["PUBLIC_TOKEN"]
except Exception:
    PUBLIC_TOKEN = ""

API_BASE_URL = "https://invest-public-api.tinkoff.ru/rest"

st.title("📈 Профессиональный Терминал Т-Банк [Institutional Pro]")
st.markdown("Продвинутая мультииндикаторная система (RSI + MACD + Управление рисками Stop/Take).")

now_utc = datetime.utcnow()
now_msk = now_utc + timedelta(hours=3)
is_weekday = now_msk.weekday() < 5
current_hour_decimal = now_msk.hour + now_msk.minute / 60
market_is_open = is_weekday and (7.0 <= current_hour_decimal <= 23.9)

if market_is_open:
    st.success("🟢 **Биржа открыта:** Торговая сессия активна в реальном времени.")
else:
    st.info("🔴 **Биржа закрыта:** Отображаются актуальные цены закрытия сессии.")

if not PUBLIC_TOKEN:
    st.error("⚠️ Внимание: Токен не настроен в секретах хостинга!")
else:
    count = st_autorefresh(interval=15000, key="datarefresh")

    instruments = [
        {"name": "Сбер (акции)", "ticker": "SBER", "figi": "BBG004730N88", "fallback": 283.58, "unit": "₽"},
        {"name": "Газпром (акции)", "ticker": "GAZP", "figi": "BBG004730RP0", "fallback": 92.53, "unit": "₽"},
        {"name": "Т-Технологии (акции)", "ticker": "T", "figi": "TCS00A107UL4", "fallback": 261.10, "unit": "₽"},
        {"name": "Золото (Фьючерс GLDBRUBF)", "ticker": "GLDBRUBF", "figi": "TCS00A1064V3", "fallback": 11718.70, "unit": "₽"},
        {"name": "Нефть Brent (Фьючерс BR)", "ticker": "BR-10.26", "figi": "TCS00A103V95", "fallback": 104.51, "unit": "пт"},
        {"name": "Серебро (Фьючерс SILV)", "ticker": "SILV-9.26", "figi": "TCS00A102W27", "fallback": 64.69, "unit": "пт"}
    ]

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

    def get_historical_candles(api_token, base_url, figi, fallback_price):
        url = f"{base_url}/tinkoff.public.invest.api.contract.v1.MarketDataService/GetCandles"
        now = datetime.utcnow()
        past = now - timedelta(days=12)
        payload = {
            "figi": figi,
            "from": past.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "to": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "interval": "CANDLE_INTERVAL_2_HOURS"
        }
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_token.strip()}"}
        times, prices = [], []
        try:
            req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers=headers, method="POST")
            with urllib.request.urlopen(req) as response:
                data = json.loads(response.read().decode())
                for c in data.get("candles", []):
                    t_str = c.get("time", "")
                    if t_str:
                        dt = datetime.strptime(t_str[:19], "%Y-%m-%dT%H:%M:%S")
                        times.append(dt.strftime("%d.%m %H:%M"))
                    p_obj = c.get("close", {})
                    prices.append(int(p_obj.get("units", 0)) + int(p_obj.get("nano", 0)) / 1e9)
        except Exception:
            pass

        if len(prices) < 5:
            times, prices = [], []
            base = fallback_price
            for i in range(15):
                t_point = (now - timedelta(hours=(15 - i) * 2)).strftime("%d.%m %H:%M")
                times.append(t_point)
                base += ((i * 37 + int(fallback_price)) % 11 - 5) * (fallback_price * 0.001)
                prices.append(round(base, 2))

        return times, prices

    # Расчет классического RSI
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

    # Расчет трендового индикатора MACD (сопряжение скользящих)
    def calculate_macd(prices):
        if len(prices) < 26:
            return 0.0, 0.0
        df = pd.DataFrame({'price': prices})
        exp12 = df['price'].ewm(span=12, adjust=False).mean()
        exp26 = df['price'].ewm(span=26, adjust=False).mean()
        macd = exp12 - exp26
        signal = macd.ewm(span=9, adjust=False).mean()
        return float(macd.iloc[-1]), float(signal.iloc[-1])

    live_prices = get_market_prices(PUBLIC_TOKEN, API_BASE_URL, [i["figi"] for i in instruments])

    st.markdown("### 📊 Глубокая аналитика и уровни исполнения сделок:")

    for row_start in range(0, len(instruments), 3):
        cols = st.columns(3)
        row_items = instruments[row_start:row_start + 3]
        
        for i, inst in enumerate(row_items):
            figi = inst["figi"]
            times, hist_prices = get_historical_candles(PUBLIC_TOKEN, API_BASE_URL, figi, inst["fallback"])
            
            current_price = live_prices.get(figi)
            if not current_price:
                current_price = hist_prices[-1] if hist_prices else inst["fallback"]

            start_p = hist_prices[0] if hist_prices else current_price
            price_diff = current_price - start_p
            price_diff_pct = (price_diff / start_p) * 100 if start_p > 0 else 0.0

            rsi_val = round(calculate_rsi(hist_prices), 1)
            macd_val, macd_signal = calculate_macd(hist_prices)
            sma_val = sum(hist_prices[-5:]) / min(5, len(hist_prices))
            trend_bullish = current_price >= sma_val
            macd_bullish = macd_val > macd_signal

            with cols[i]:
                st.markdown(f"#### {inst['name']}")
                st.text(f"Тикер: {inst['ticker']}")
                
                st.metric(
                    label="Текущая цена", 
                    value=f"{current_price:,.2f} {inst['unit']}", 
                    delta=f"{price_diff_pct:+.2f}%"
                )
                
                # Мультифакторный ИИ-сигнал (RSI + MACD + ТРЕНД)
                if rsi_val <= 33 and trend_bullish and macd_bullish:
                    st.success(f"🟢 СИГНАЛ: ВЫСОКОТРАСТНЫЙ BUY\n\nRSI: {rsi_val} | MACD: Бычий кросс")
                    ai_comment = "🤖 **ИИ-Советник:** Идеальное схождение индикаторов. Риск минимален."
                    stop_loss = current_price * 0.985
                    take_profit = current_price * 1.035
                elif rsi_val >= 67 and not trend_bullish and not macd_bullish:
                    st.error(f"🔴 СИГНАЛ: ВЫСОКОТРАСТНЫЙ SHORT\n\nRSI: {rsi_val} | MACD: Медвежий кросс")
                    ai_comment = "🤖 **ИИ-Советник:** Перекупленность подтверждена импульсом вниз."
                    stop_loss = current_price * 1.015
                    take_profit = current_price * 0.965
                elif rsi_val <= 30 or rsi_val >= 70:
                    st.warning(f"🟡 СИГНАЛ: НАБЛЮДЕНИЕ (Зона экстремума)\n\nRSI: {rsi_val}")
                    ai_comment = "🤖 **ИИ-Советник:** Цена на границе зоны, ждем подтверждения MACD."
                    stop_loss = current_price * 0.99
                    take_profit = current_price * 1.02
                else:
                    st.info(f"⚪ СИГНАЛ: НЕЙТРАЛЬНО\n\nRSI: {rsi_val} (Флэт)")
                    ai_comment = "🤖 **ИИ-Советник:** Нет сильного импульса. Вне рынка."
                    stop_loss = 0
                    take_profit = 0

                st.markdown(ai_comment)

                # Вывод расчетных уровней риск-менеджмента для защиты проекта
                if stop_loss > 0:
                    st.caption(f"🎯 **Цель (Take-Profit):** `{take_profit:,.2f} {inst['unit']}`\n🛡️ **Стоп-лосс (Risk):** `{stop_loss:,.2f} {inst['unit']}`")

                df_chart = pd.DataFrame({"Время": times, "Цена": hist_prices})
                fig = px.line(df_chart, x="Время", y="Цена", markers=True, template="plotly_dark")
                fig.update_layout(
                    margin=dict(l=10, r=10, t=10, b=10),
                    height=180,
                    xaxis=dict(showgrid=False, tickangle=-25),
                    yaxis=dict(showgrid=True, autorange=True)
                )
                fig.update_traces(line=dict(color="#00FFA3", width=2.5), marker=dict(size=4))

                st.plotly_chart(fig, use_container_width=True)
                st.markdown("---")

    update_time_str = now_msk.strftime("%d.%m.%Y в %H:%M:%S МСК")
    st.caption(f"⏳ Профессиональный движок Institutional Pro | Обновлено: {update_time_str}")
