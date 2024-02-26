import logging
import os
import requests
import asyncio
from telegram import Update, Bot
from telegram.ext import Updater, CommandHandler, CallbackContext, Application, CommandHandler
from cachetools import TTLCache

# Setup basic logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Cache setup for circulating supply (24 hours TTL)
circulating_supply_cache = TTLCache(maxsize=1, ttl=86400)  # 86400 seconds = 24 hours
# Cache setup for MEXC price data (5 minutes TTL)
price_cache = TTLCache(maxsize=1, ttl=300)  # 300 seconds = 5 minutes

# Environment variables for configuration
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
MEXC_MARKET_URL = 'http://mexc.com/open/api/v2/market/ticker'
CIRCULATING_SUPPLY_URL = "https://api.andromedaprotocol.io/v1/chain/circulating_supply.json"

# Function to get ANDR's circulating supply with caching
async def get_circulating_supply():
    if 'circulating_supply' in circulating_supply_cache:
        return circulating_supply_cache['circulating_supply']
    try:
        response = requests.get(CIRCULATING_SUPPLY_URL, timeout=10)
        response.raise_for_status()  # Raises an exception for 4XX or 5XX errors
        circulating_supply = response.json()  # Directly using the response as it's already an integer
        circulating_supply_cache['circulating_supply'] = circulating_supply
        return circulating_supply
    except Exception as e:
        logger.error(f"Error fetching circulating supply: {e}")
        return None

# Function to greet users and explain commands
async def start(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text(
        "Welcome to the ANDR Market Cap Bot! 🚀\n\n"
        "Use the command /marketcap to get the current market cap of ANDR.\n\n"
        "Just type or tap on /marketcap to get started!"
    )



# Function to get ANDR's price from MEXC
async def get_andr_price():
    if 'andr_price' in price_cache:
        return price_cache['andr_price']
    try:
        params = {'symbol': 'ANDR_USDT'}
        response = requests.get(MEXC_MARKET_URL, params=params, timeout=10)
        response.raise_for_status()
        response_json = response.json()
        last_price = float(response_json['data'][0]['last'])
        price_cache['andr_price'] = last_price
        return last_price
    except Exception as e:
        logger.error(f"Error fetching ANDR price: {e}")
        return None


# Command handler function for market cap
async def market_cap(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text("Calculating ANDR market cap, please wait...")
    circulating_supply = await get_circulating_supply()
    last_price = await get_andr_price()
    
    if circulating_supply is None or last_price is None:
        await update.message.reply_text("Failed to fetch data, please try again later.")
        return

    market_cap = circulating_supply * last_price
        # Round the market cap to 0 decimal places
    rounded_market_cap = round(market_cap)
    # Format with a dollar sign
    formatted_market_cap = f"${rounded_market_cap:,}"
    
    await update.message.reply_text(f'ANDR Market Cap: {formatted_market_cap}')

# Main function to run the bot
def main():
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # Add start command handler
    application.add_handler(CommandHandler("start", start))
    
    # Add marketcap command handler
    application.add_handler(CommandHandler("marketcap", market_cap))

    application.run_polling()

if __name__ == '__main__':
    main()

