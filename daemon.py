import json
import datetime
import threading
import time
import pandas as pd
from pybit.unified_trading import WebSocket
import websocket
from tinydb import TinyDB, Query

base = "USDC"
quote = "USDT"
instrument = base + quote
DEBUG = not True
ohlcv = pd.DataFrame(columns=["date","Open","High","Low","Close","Volume"])


def handle_message_bybit(message):
    handle_message(ws,message)
    
def handle_message_backtest(m):
    message = json.loads(m)
    handle_message(ws,message)

def handle_message(ws,message):
    try:
        #websocket.dump("msg",message)
        d = datetime.datetime.fromtimestamp(message['data'][0]['start']/1000)
        o = float(message['data'][0]['open'])
        h = float(message['data'][0]['high'])
        l = float(message['data'][0]['low'])
        c = float(message['data'][0]['close'])
        v = float(message['data'][0]['volume'])
        db.insert(message['data'][0])

    except Exception as ex:
        print((str(ex)))
        print(str(ex.__traceback__.tb_lasti))

def on_message(ws, message):
    print(message)

def on_message_wsapp(wsapp, message):
    print(message)

def on_error(ws, error):
    print(error)

def on_close(ws, close_status_code, close_msg):
    print("### closed ###")

def on_open(ws):
    print("Opened connection")

def on_data(ws,data):
    print(data)

def run_kline():
    ws.kline_stream(
            interval=1,
            symbol=instrument,
            callback=handle_message_bybit)

try:

    db = TinyDB('ohlcv.json')

    websocket.enableTrace(True)
    if (not DEBUG):
        ws = WebSocket(
        channel_type="spot",
        testnet=False,
        api_key="tOkx1lElyxcjnegbFw",
        api_secret="i9qYG3cVycnZCAWdBR0WVa6FcZlYvsnzpicP",

       )
        producer = threading.Thread(target=run_kline)
        producer.start()
    else:    
        ws = websocket.WebSocketApp("ws://localhost:8765", on_message=handle_message_backtest)
        ws.run_forever() 


except Exception as e:
    print((str(e)))
    print(str(e.__traceback__.tb_lineno))

while True:
    time.sleep(1)