import asyncio
import csv
import datetime
import os
import sys
import time
import traceback
from altair import CsvDataFormat
import websockets
import json
import pandas as pd
root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(root + '/python')
sys.path.append(sys.path[0] + '/../class')
from Position import Position

path = "../data/bybit/USDC/data_1M_20230701_1m.csv"
df = None
i = 0
message = {"data":""}
async def echo(websocket):
    async for message in websocket:
        response = {
            'error': None,
            'result': message
        }
        await websocket.send(json.dumps(response))

async def send(websocket):
    global i
    try:
        while i <= df.size-1:
            d = df.iloc[i,0]
            element = datetime.datetime.strptime(d,"%Y-%m-%d %H:%M:%S")
            t = datetime.datetime.timestamp(element)
            o = df.iloc[i,1]
            h = df.iloc[i,2]
            l = df.iloc[i,3]
            c = df.iloc[i,4]
            v = df.iloc[i,5]
            
            position = Position(d,o,h,l,c,v)
            i +=1            
            message["data"] = [{"start":t*1000,"open":position.open,"high":position.high,"low":position.low,"close":position.close,"volume":position.volume}]

            await websocket.send(json.dumps(message))
            time.sleep(60)

    except Exception as e:
        traceback.format_exc()
        print(str(e))

async def main():
    try:
        async with websockets.serve(send, "localhost", 8765):
            await asyncio.Future()  # run forever
    except Exception as e:
        traceback.format_exc()
        print(str(e))

def init():
    global df
    try:
        # decoding the JSON to dictionay
        df = pd.read_csv(path,delimiter=',')

    except Exception as e:
        traceback.format_exc()
        print(str(e))

    


init()    
asyncio.run(main())