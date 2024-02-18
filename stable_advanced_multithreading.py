#!/usr/bin/env python
# -*- coding: utf-8 -*- 
import time
import os
import sys

root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(root + '/python')
sys.path.append(sys.path[0] + '/class')
from Wallet import Wallet
from Common import Common
from strategy import Strategy

from pybit.unified_trading import HTTP

from Timer import Timer
import threading



# A editer
# compte principal
api_key="tOkx1lElyxcjnegbFw",
api_secret="i9qYG3cVycnZCAWdBR0WVa6FcZlYvsnzpicP",
# compte trading
api_key = "1FiaRE830E7mHquuGD"
api_secret = "Tgh3JJ1XmvMFF292VOEAmkZQsEp4JLiKbVEu"
#testnet
'''
testnet=True,
channel_type="spot",
api_key = "3KBEJYOE4NhdkTw2db",
api_secret="L2kGWggYMgh0mcHzaqc34Nz9cGvzwTuIrNnu"
'''

consumer = None
session = HTTP(
    #mainnet
    testnet=False,
    api_key=api_key,
    api_secret=api_secret,
)
walletmanager = Wallet(session)
common = Common(walletmanager)
base = common.base
quote = common.quote

instrument = base + quote
DEBUG = not True
done = False


reference = common.reference

s = Strategy(1000,1,15,3,reference,10,10,10,10,base,quote,session,common)
timer = Timer()

begin = time.time()


def main():
    global consumer

while consumer is None or s.done:
    consumer = threading.Thread(target=s.process)
    consumer.start()
    s.done = False
    end = time.time()
    elapsed = end-begin