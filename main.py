import logging
import os
import asyncio
import aiohttp
from telegram.ext import Application, CommandHandler, ContextTypes
from cachetools import TTLCache
from aiohttp_retry import RetryClient, ExponentialRetry
from telegram import Update

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

circulating_supply_cache = TTLCache(maxsize=1, ttl=86400)  # 24-hour cache
price_cache = TTLCache(maxsize=1, ttl=300)  # 5-minute cache

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
MEXC_MARKET_URL = 'https://mexc.com/open/api/v2/market/ticker'
CIRCULATING_SUPPLY_URL = "https://api.andromedaprotocol.io/v1/chain/circulating_supply.json"

async def fetch_url_with_retries(session, url, params=None):
    retry_options = ExponentialRetry(attempts=3, factor=0.5)
    async with RetryClient(session, retry_options=retry_options) as retry_client:
        async with retry_client.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as response:
            if response.status == 200:
                return await response.json()
            logger.error(f"HTTP Error {response.status} for {url}")
            return None

async def get_circulating_supply():
    async with aiohttp.ClientSession() as session:
        data = await fetch_url_with_retries(session, CIRCULATING_SUPPLY_URL)
        if data is not None:
            try:
                # Assuming the API directly returns an integer as the response body
                circulating_supply = float(data)
                circulating_supply_cache['circulating_supply'] = circulating_supply
                return circulating_supply
            except ValueError:
                # Log the error if conversion to float fails
                logger.error("Failed to convert circulating supply to float")
        else:
            logger.error("Failed to fetch or validate circulating supply")
        
        # Return cached value if fetch fails
        return circulating_supply_cache.get('circulating_supply')


async def get_andr_price():
    async with aiohttp.ClientSession() as session:
        data = await fetch_url_with_retries(session, MEXC_MARKET_URL, {'symbol': 'ANDR_USDT'})
        if data and 'data' in data and len(data['data']) > 0:
            try:
                last_price = float(data['data'][0]['last'])
                price_cache['andr_price'] = last_price
                return last_price
            except (ValueError, KeyError, TypeError):
                logger.error("Failed to parse ANDR price from response")
        logger.error("Failed to fetch ANDR price or invalid data format")
        return price_cache.get('andr_price')

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await context.bot.send_message(chat_id=update.effective_chat.id,
                                   text="Welcome to the ANDR Market Cap Bot! 🚀\n\n"
                                        "Use /marketcap to get the current market cap of ANDR.")

async def market_cap(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    circulating_supply = await get_circulating_supply()
    last_price = await get_andr_price()

    if circulating_supply is None or last_price is None:
        await update.message.reply_text("Failed to fetch data, please try again later.")
        return

    market_cap = circulating_supply * last_price
    formatted_market_cap = f"${market_cap:,.0f}"
    await update.message.reply_text(f'ANDR Market Cap: {formatted_market_cap}')

def main():
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("marketcap", market_cap))
    application.run_polling()

if __name__ == '__main__':
    asyncio.run(main())
