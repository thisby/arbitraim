import asyncio
import math
import os
from random import randint
import sys
from pprint import pprint
import time
import traceback
import pandas as pd
import csv

root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(root + '/python')

import ccxt.async_support as ccxt  # noqa: E402

exchange = ccxt.bybit({
    'apiKey': 'tOkx1lElyxcjnegbFw',
    'secret': 'i9qYG3cVycnZCAWdBR0WVa6FcZlYvsnzpicP',
})
current_ohlcv = pd.DataFrame()
variation = 0.0001
symbol = 'DAI/USDT'
base = symbol.split('/')[0]
quote = symbol.split('/')[1]
symbols = [ symbol ]
candle_waiting = 30
last_order = {
    "id":0,
    "price":0,
    "amount":0,
    "timestamp":0
}
first_trade = 0

def __get_is_first_trade__():
    global first_trade
    return first_trade

def __set_is_first_trade__(value):
    global first_trade
    first_trade = value
    return first_trade

def __get_adjust_price_counter__():
    global adjust_price_counter
    return adjust_price_counter

def __set_adjust_price_counter__(value):
    global adjust_price_counter
    adjust_price_counter = value
    return adjust_price_counter

def __inc_adjust_price_counter__():
    global adjust_price_counter
    adjust_price_counter += 1

async def swap_from_usdt():
    global first_trade

    exchange.options['defaultType'] = 'spot'; # very important set swap as default type
    markets = await exchange.load_markets(True)

    balanceParams = {
        'settle': 'USDT'        
    }
    balance = await exchange.fetch_balance(balanceParams)
    print(round(balance[quote]['free'],5))
    usdt = balance[quote]['free']

    positions = []
    type = 'limit'
    side = 'buy'
    params  = {
        'timeInForce':'IOC'
    }
    price = await adjust_price()
    try:        
        if quote not in balance or balance[quote]['free'] < 1:
            return
        #tant qu'on a pas réussi a acheter
        while base not in balance or balance[base]['free'] < 1:
            if (__get_is_first_trade__() or adjust_price_counter >= candle_waiting):            
                price = await adjust_price() # adjust this accordingly
                if (not __get_is_first_trade__()): __set_adjust_price_counter__(0)
            # ce n'est pas le premier trade et le compteur est inférieur au delta des ticks
            if (not __get_is_first_trade__() and adjust_price_counter < candle_waiting) : __inc_adjust_price_counter__()
                
            amount = usdt/price

            entry_order = await exchange.create_order(symbol, type, side, amount, price,params)
            balance = await exchange.fetch_balance(balanceParams)
            time.sleep(1)
        
        last_order["price"] = entry_order['price']
        last_order["amount"] = entry_order['amount']
        last_order["timestamp"] = entry_order['timestamp']
        last_order["id"] = entry_order['id']

        print('Create order id:', entry_order['id'])
        return entry_order
    except Exception as e:
        traceback.format_exc()
        print(str(e))

async def swap_to_usdt():
    # Close position (assuming it was already opened) by issuing an order in the opposite direction
    side = 'sell'
    type = 'limit'
    params = {
        'reduce_only': True,
        'timeInForce':'IOC'
    }

    balance = await exchange.fetch_balance()
    amount = balance[base]['free'] if base in balance and balance[base]['free'] > 1 else 0
    # rien n'est vendable...
    if amount == 0:
        return
    
    price = last_order['price']
    price += variation
    exit_order = {}
    while quote not in balance or balance[quote]['free'] < 1:
        time.sleep(1)
        # cas exceptionnel ou on n'a pas de dernier prix, on va chercher le dernier prix de vente
        if last_order['price'] == 0:
            price = await adjust_price()
        exit_order = await exchange.createOrder(symbol, type, side, amount, price, params)
        balance = await exchange.fetch_balance()

    last_order["price"] = exit_order['price']
    last_order["amount"] = exit_order['amount']
    last_order["timestamp"] = exit_order['timestamp']
    last_order["id"] = exit_order['id']

    return exit_order

async def adjust_price():
    global first_trade
    try:
            ohlcv = await exchange.fetch_ohlcv(symbol, '1m', None,candle_waiting+1)
            current_ohlcv = pd.DataFrame(ohlcv)
            if __get_is_first_trade__():
                __set_is_first_trade__(False)
                return (ohlcv[0][1] + ohlcv[0][4]) / 2
            else:
                __set_is_first_trade__(True)
                return ohlcv[0][3]
            
    except Exception as e:
        print(str(e))
        # raise e  # uncomment to break all loops in case of an error in any one of them
        # break  # you can break just this one loop if it fails


def retry_fetch_ohlcv(exchange, max_retries, symbol, timeframe, since, limit):
    num_retries = 0
    try:
        num_retries += 1
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe, since, limit)
        # print('Fetched', len(ohlcv), symbol, 'candles from', exchange.iso8601 (ohlcv[0][0]), 'to', exchange.iso8601 (ohlcv[-1][0]))
        return ohlcv
    except Exception:
        if num_retries > max_retries:
            raise  # Exception('Failed to fetch', timeframe, symbol, 'OHLCV in', max_retries, 'attempts')


def scrape_ohlcv(exchange, max_retries, symbol, timeframe, since, limit):
    timeframe_duration_in_seconds = exchange.parse_timeframe(timeframe)
    timeframe_duration_in_ms = timeframe_duration_in_seconds * 1000
    timedelta = limit * timeframe_duration_in_ms
    now = exchange.milliseconds()
    all_ohlcv = []
    fetch_since = since
    while fetch_since < now:
        ohlcv = retry_fetch_ohlcv(exchange, max_retries, symbol, timeframe, fetch_since, limit)
        fetch_since = (ohlcv[-1][0] + 1) if len(ohlcv) else (fetch_since + timedelta)
        all_ohlcv = all_ohlcv + ohlcv
        if len(all_ohlcv):
            print(len(all_ohlcv), 'candles in total from', exchange.iso8601(all_ohlcv[0][0]), 'to', exchange.iso8601(all_ohlcv[-1][0]))
        else:
            print(len(all_ohlcv), 'candles in total from', exchange.iso8601(fetch_since))
    return exchange.filter_by_since_limit(all_ohlcv, since, None, key=0)


def write_to_csv(filename, data):
    with open(filename, mode='w') as output_file:
        csv_writer = csv.writer(output_file, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
        csv_writer.writerows(data)


def scrape_candles_to_csv(filename, exchange_id, max_retries, symbol, timeframe, since, limit):
    # convert since from string to milliseconds integer if needed
    if isinstance(since, str):
        since = exchange.parse8601(since)
    # preload all markets from the exchange
    exchange.load_markets()
    # fetch all candles
    ohlcv = scrape_ohlcv(exchange, max_retries, symbol, timeframe, since, limit)
    # save them to csv file
    write_to_csv(filename, ohlcv)
    print('Saved', len(ohlcv), 'candles from', exchange.iso8601(ohlcv[0][0]), 'to', exchange.iso8601(ohlcv[-1][0]), 'to', filename)


async def main():
    print('CCXT Version:', ccxt.__version__)
    global first_trade
    global adjust_price_counter

    adjust_price_counter = 0
    first_trade = True
    try:
        while True:
            res = await swap_from_usdt()
            res = await swap_to_usdt()            
    except Exception as e:
        print(e)
    # await exchange.close()
    
asyncio.run(main())

