import streamlit as st
import aiohttp
import asyncio
from datetime import datetime, timedelta

BINANCE_BASE_URL = "https://api.binance.com"
FUTURES_BASE_URL = "https://fapi.binance.com"

async def fetch_json(session, url):
    try:
        async with session.get(url) as response:
            return await response.json()
    except Exception as e:
        st.error(f"Error fetching {url}: {e}")
        return {}

async def get_usdt_pairs(session, is_futures=False):
    url = f"{FUTURES_BASE_URL}/fapi/v1/exchangeInfo" if is_futures else f"{BINANCE_BASE_URL}/api/v3/exchangeInfo"
    data = await fetch_json(session, url)

    if 'symbols' not in data:
        st.warning(f"Unexpected response from Binance {'Futures' if is_futures else 'Spot'} API:\n{data}")
        return []

    return [
        s['symbol'] for s in data['symbols']
        if s.get('quoteAsset') == 'USDT' and s.get('status') == 'TRADING'
    ]

async def get_funding_rates(session):
    url = f"{FUTURES_BASE_URL}/fapi/v1/premiumIndex"
    data = await fetch_json(session, url)

    if not isinstance(data, list):
        st.warning("Unexpected funding rate data:\n" + str(data))
        return {}

    return {
        entry['symbol']: float(entry.get('lastFundingRate', 0))
        for entry in data
        if entry.get('symbol', '').endswith('USDT')
    }

async def run_screener():
    async with aiohttp.ClientSession() as session:
        spot_symbols = await get_usdt_pairs(session, is_futures=False)
        futures_symbols = await get_usdt_pairs(session, is_futures=True)
        funding_rates = await get_funding_rates(session)

        return spot_symbols, futures_symbols, funding_rates

def display_results(spot, futures, frs):
    st.title("📊 Binance Screener (Spot / Futures / Funding Rates)")
    st.subheader("🔹 Spot USDT Pairs")
    st.write(f"Found {len(spot)} spot symbols.")
    st.write(spot[:20])  # show first 20

    st.subheader("🔸 Futures USDT Pairs")
    st.write(f"Found {len(futures)} futures symbols.")
    st.write(futures[:20])  # show first 20

    st.subheader("💰 Funding Rates (Top 10 by Rate)")
    sorted_rates = sorted(frs.items(), key=lambda x: abs(x[1]), reverse=True)[:10]
    for symbol, rate in sorted_rates:
        st.write(f"{symbol}: {rate * 100:.4f}%")

if __name__ == "__main__":
    try:
        spot, futures, frs = asyncio.run(run_screener())
        display_results(spot, futures, frs)
    except Exception as e:
        st.error(f"App crashed: {e}")
