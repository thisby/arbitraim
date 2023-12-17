#!/usr/bin/env python
# -*- coding: utf-8 -*- 
import datetime
import time
import pandas as pd
import os
import sys
from dateutil import tz 
root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(root + '/python')
sys.path.append(sys.path[0] + '/class')
from strategy import Strategy

from pybit.unified_trading import HTTP

from Reference import Reference
from Timer import Timer
import threading

consumer = None
base = "USDC"
quote = "USDT"
instrument = base + quote
DEBUG = not True
done = False

# A editer
# compte principal
api_key="tOkx1lElyxcjnegbFw",
api_secret="i9qYG3cVycnZCAWdBR0WVa6FcZlYvsnzpicP",
# compte trading
api_key = "WMQ7ZAe2DIQNMjPoSE"
api_secret = "Qe7lJGokH8OPphTI2EHkR54RXkOkPMIp1C4F"



#testnet
'''
testnet=True,
channel_type="spot",
api_key = "3KBEJYOE4NhdkTw2db",
api_secret="L2kGWggYMgh0mcHzaqc34Nz9cGvzwTuIrNnu"
'''

session = HTTP(
    #mainnet
    testnet=False,
    api_key=api_key,
    api_secret=api_secret,
)

s = Strategy(1000,1,3,3,Reference.OPEN,10,10,10,10,base,quote,session)
timer = Timer()

begin = time.time()


def main():
    global consumer

while consumer is None or s.done:
    consumer = threading.Thread(target=s.process)
    consumer.start()
    s.done = False
    # time.sleep(18000)
    if s.passage % 30 == 0 and len(s.trades) > 0:
        s.trades_persist()
    s.passage += 1
    end = time.time()
    elapsed = end-begin