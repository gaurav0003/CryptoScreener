import asyncio
import aiohttp
import pandas as pd
from datetime import datetime
import streamlit as st

# Binance endpoints
SPOT_URL = "https://api.binance.com"
FUTURES_URL = "https://fapi.binance.com"

# Streamlit UI
st.title("📈 Crypto Pattern Screener")
TIMEFRAME = st.selectbox("Select Timeframe", ["15m", "30m", "1h", "2h", "4h"])

pattern_map = {
    "Hammer": "hammer",
    "Shooting Star": "shooting_star",
    "Bullish Engulfing": "bullish_engulfing",
    "Bearish Engulfing": "bearish_engulfing",
    "Morning Star": "morning_star",
    "Evening Star": "evening_star",
    "Piercing Line": "piercing_line",
    "Dark Cloud Cover": "dark_cloud_cover"
}
pattern_choice = st.selectbox("Select Candlestick Pattern", list(pattern_map.keys()))
PATTERN = pattern_map[pattern_choice]

# Function to detect candlestick patterns
def detect_candle(candles, pattern):
    if len(candles) < 3:
        return False

    c1 = list(map(float, candles[-3][1:5]))
    c2 = list(map(float, candles[-2][1:5]))
    c3 = list(map(float, candles[-1][1:5]))

    o1, h1, l1, c1c = c1
    o2, h2, l2, c2c = c2
    o3, h3, l3, c3c = c3

    body1 = abs(c1c - o1)
    body2 = abs(c2c - o2)
    body3 = abs(c3c - o3)

    upper_wick = h3 - max(o3, c3c)
    lower_wick = min(o3, c3c) - l3

    if pattern == "hammer":
        return lower_wick > 2 * body3 and upper_wick < body3

    if pattern == "shooting_star":
        return upper_wick > 2 * body3 and lower_wick < body3

    if pattern == "bullish_engulfing":
        return c2c < o2 and c3c > o3 and o3 < c2c and c3c > o2

    if pattern == "bearish_engulfing":
        return c2c > o2 and c3c < o3 and o3 > c2c and c3c < o2

    if pattern == "morning_star":
        return c1c < o1 and abs(o2 - c2c) < body1 * 0.5 and c3c > o3 and c3c > (o1 + c1c) / 2

    if pattern == "evening_star":
        return c1c > o1 and abs(o2 - c2c) < body1 * 0.5 and c3c < o3 and c3c < (o1 + c1c) / 2

    if pattern == "piercing_line":
        return c2c < o2 and c3c > o3 and o3 < c2c and c3c > (o2 + c2c) / 2

    if pattern == "dark_cloud_cover":
        return c2c > o2 and c3c < o3 and o3 > c2c and c3c < (o2 + c2c) / 2

    return False

def calculate_percentage_change(open_, close):
    return round(((float(close) - float(open_)) / float(open_)) * 100, 2)

async def fetch_funding_rates(session):
    url = f"{FUTURES_URL}/fapi/v1/premiumIndex"
    async with session.get(url) as resp:
        data = await resp.json()
        return {item['symbol']: float(item['lastFundingRate']) * 100 for item in data}

async def get_usdt_pairs(session, is_futures=False):
    url = f"{FUTURES_URL}/fapi/v1/exchangeInfo" if is_futures else f"{SPOT_URL}/api/v3/exchangeInfo"
    async with session.get(url) as resp:
        data = await resp.json()
        return [
            s['symbol'] for s in data['symbols']
            if s['quoteAsset'] == 'USDT' and s['status'] == 'TRADING'
        ]

async def fetch_klines(session, symbol, interval, is_futures=False, limit=3):
    base_url = FUTURES_URL if is_futures else SPOT_URL
    url = f"{base_url}/fapi/v1/klines" if is_futures else f"{base_url}/api/v3/klines"
    url += f"?symbol={symbol}&interval={interval}&limit={limit}"
    try:
        async with session.get(url, timeout=10) as resp:
            return await resp.json()
    except:
        return []

async def fetch_and_check(session, symbol, timeframe, pattern, is_futures=False):
    candles = await fetch_klines(session, symbol, timeframe, is_futures, limit=3)
    if isinstance(candles, list) and len(candles) >= 3:
        if detect_candle(candles, pattern):
            open_, close = candles[-1][1], candles[-1][4]
            tf_change = calculate_percentage_change(open_, close)
            long_candles = await fetch_klines(session, symbol, "1d", is_futures, limit=2)
            if isinstance(long_candles, list) and len(long_candles) >= 2:
                open24, close24 = long_candles[-1][1], long_candles[-1][4]
                long_change = calculate_percentage_change(open24, close24)
                return {"symbol": symbol, "change": tf_change, "24h": long_change}
    return None

async def run_screener():
    async with aiohttp.ClientSession() as session:
        spot_symbols = await get_usdt_pairs(session, is_futures=False)
        futures_symbols = await get_usdt_pairs(session, is_futures=True)
        funding_rates = await fetch_funding_rates(session)

        spot_tasks = [
            fetch_and_check(session, symbol, TIMEFRAME, PATTERN, is_futures=False)
            for symbol in spot_symbols
        ]
        futures_tasks = [
            fetch_and_check(session, symbol, TIMEFRAME, PATTERN, is_futures=True)
            for symbol in futures_symbols
        ]

        spot_results = await asyncio.gather(*spot_tasks)
        futures_results = await asyncio.gather(*futures_tasks)

        spot_matches = [s for s in spot_results if s]
        futures_matches = [s for s in futures_results if s]

        spot_matches.sort(key=lambda x: x['change'], reverse=True)
        futures_matches.sort(key=lambda x: x['change'], reverse=True)

        return spot_matches, futures_matches, funding_rates

if st.button("🔍 Run Screener"):
    with st.spinner("Scanning markets..."):
        spot, futures, frs = asyncio.run(run_screener())

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        st.success(f"✅ Scan complete at {now}")
        st.markdown(f"### Pattern: **{pattern_choice}** | Timeframe: **{TIMEFRAME}**")

        if spot:
            st.markdown("#### 📈 Spot Matches")
            st.dataframe(pd.DataFrame(spot[:20]))
        else:
            st.warning("No matches found in Spot Market.")

        if futures:
            st.markdown("#### 📉 Futures Matches (with Funding Rate)")
            for f in futures[:20]:
                f["funding_rate"] = round(frs.get(f["symbol"], 0.0), 4)
            st.dataframe(pd.DataFrame(futures[:20]))
        else:
            st.warning("No matches found in Futures Market.")
