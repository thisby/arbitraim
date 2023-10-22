#!/usr/bin/env python
# -*- coding: utf-8 -*- 
import datetime
import json
from tinydb import TinyDB, Query
from pynput.keyboard import Key, Listener
import time
import pandas as pd
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import rel
import sys
from dateutil import tz 
root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(root + '/python')
sys.path.append(sys.path[0] + '/class')
import asyncio
import websocket
from pybit.unified_trading import HTTP,WebSocket
from Mail_Subject import Mail_Subject
from Reference import Reference
from Position import Position


# A editer
# compte principal
api_key="tOkx1lElyxcjnegbFw",
api_secret="i9qYG3cVycnZCAWdBR0WVa6FcZlYvsnzpicP",
# compte trading
api_key = "WMQ7ZAe2DIQNMjPoSE"
api_secret = "Qe7lJGokH8OPphTI2EHkR54RXkOkPMIp1C4F"
base = "USDC"
pips = 1/10000
MIN_SHARES_REQUIRED = 9
MAX_RUNNING_TIME = 300
DEBUG = not True
MODE = 0 # 1 for cool mode (low price selling), 0 for aggressive (entry price selling)
# Fin



def send_email(mail_subject):
    try:
        if mail_subject.name not in texts:
            return

        d = texts[mail_subject.name]

        server = smtplib.SMTP(smtp_server, smtp_port)
        msg['Subject'] = d['subject']
        msg.attach(MIMEText(d['body'], 'html'))
        server.ehlo()
        # server.starttls()  # Utilisez TLS (Transport Layer Security) pour la sécurité
        server.login(smtp_username, smtp_password)
        text = msg.as_string()
        server.sendmail(smtp_username, msg['To'], text)
        server.quit()
        print(f'{mail_subject.name} - E-mail envoyé avec succès.')
    except Exception as e:
        print('Erreur lors de l\'envoi de l\'e-mail :', str(e))
        print(e.__traceback__.tb_lineno)

class Strategy():

    '''
    b : balance
    q: volume quota
    msw : Temps d'attente maximum avant vente forcé
    msb : Temps d'attente minimum avant réajustement prix achat
    r : reference de prix pour prix d'achat (ohlc)
    bvd: Variation de référence après achat réussi , en vue d'un krack ou assimilé,
    svd: Variation de référence après vente réussi , en vue d'un krack ou assimilé,
    bvp: Variation de référence après achat réussi , en vue d'un pump ou assimilé,
    svp: Variation de référence après vente réussi , en vue d'un pump ou assimilé,
    i: Instrument de trading
    '''
    def __init__(self,b,q,msw,mbw,r,svd,bvd,svp,bvp,i):
        self.balance = b
        self.passage = 0
        self.first_use_case_date = datetime.datetime.now()
        self.buy_variation_dump = bvd
        self.sell_variation_dump = svd
        self.buy_variation_pump = bvp
        self.sell_variation_pump = svp
        self.now = datetime.datetime.min
        self.quota = q
        self.ref = r
        self.checkVolume = False
        self.pips = pips
        self.instrument = i
        self.max_sell_wait = msw
        self.max_buy_wait = mbw
        self.runDate = datetime.datetime.now()
        self.avgVolume = 0
        self.dataframe = self.dataframe_init()

    def get_balance(self,token):
        global session
        try:            
            assets = session.get_coin_balance(
            accountType="UNIFIED",
            coin=token,
            )
            return float(assets['result']['balance']['walletBalance'])
        except Exception as e:
            print(str(e))

    def get_wallet_balance(self):
        global session
        try:
            balance = session.get_wallet_balance(accountType="UNIFIED")
            self.balance = balance["totalEquity"]
            return balance
        except Exception as e:
            print(str(e))


    def process(self,position):
        global last_entry_price,last_exit_price,low,sum,dataframe,session,row,trades,buy_counter,sell_counter
        # dataframe = self.dataframe_init()
        ref = self.ref
        buy_variation_dump = self.buy_variation_dump
        buy_variation_pump = self.buy_variation_pump

        e = 0

        e = self.switch_price_reference(ref, position.open, position.high, position.low, position.close)
        
        if low == 0:
            low = position.low

        self.manage_alerts(position, buy_variation_dump, buy_variation_pump)

        position.shares = self.get_balance(base)
        # d = self.get_wallet_balance()
        self.balance = self.get_balance(quote)

        if position.shares is not None and position.shares > MIN_SHARES_REQUIRED:
            if last_entry_price == 0:
                #get the last price in db
                Trade = Query()
                all = self.trades.search(Trade.type == "B")
                if len(all) > 0:
                    doc = all[-1]
                    last_entry_price = doc["entry_price"]

            if last_entry_price == 0:
                #try to get the last entry with bybit request
                orders = session.get_order_history(
                    category="spot",
                    limit=50, 
                    orderStatus="Filled"
                    # symbol=base                       
                )
                filtered = filter(lambda x:x["side"] == "Buy",orders['result']['list'])
                l = list(filtered)
                stats = {"avgPrice":"","symbol":instrument}
                if (len(l) > 0):
                    stats = l[0]                 
                

                if stats['symbol'] == instrument:                        
                    avgPrice = stats['avgPrice']
                    # status = stats['orderStatus']
                    if avgPrice not in ("",0,'0'):
                        avgPrice = float(avgPrice)
                        # insert last buy trade in db
                    else:
                        avgPrice = position.low
                    last_entry_price = avgPrice
                    if last_exit_price == 0:
                        last_exit_price = avgPrice + self.pips
            else:
                last_exit_price = last_entry_price+self.pips

            result = self.exit_position( position)
            orderId = result['result']['orderId']
            order = session.get_order_history(
                category="spot",
                limit=1,                        
                orderId=orderId
            )
            stats = order['result']['list'][0]
            avgPrice = stats['avgPrice']
            status = stats['orderStatus']
            shares = float(stats['qty'])
            row.update({"orderId":orderId})

            if avgPrice != "" and status != "Cancelled":
                avgPrice = float(avgPrice)
                last_entry_price = avgPrice
                last_exit_price = avgPrice + self.pips
                row.update({"status":'filled'})
                sell_counter = 0
                cost = last_entry_price*shares                
                earn = last_exit_price*shares
                sum += earn - cost
                if sum < -10:
                   send_email(Mail_Subject.NEGATIVE_GAIN)
                   exit()


            else:
                row.update({"status":'cancelled'})
                sell_counter += 1
                if sell_counter > self.max_sell_wait:
                    sell_counter = 0
                    low = position.low
                    last_exit_price = low if MODE == 1 else last_entry_price
                    last_entry_price = last_exit_price-self.pips
            self.trades.insert(row)        
            trades.append(row) 
            row = {}  

        else:        
            result = self.entry_position( position.date, position.open, position.low, position.volume, e)
            orderId = result['result']['orderId']
            order = session.get_order_history(
                category="spot",
                limit=1,                        
                orderId=orderId
            )
            
            stats = order['result']['list'][0]
            avgPrice = stats['avgPrice']
            status = stats['orderStatus']
            row.update({"orderId":orderId})

            if avgPrice != "" and status != "Cancelled":
                avgPrice = float(avgPrice)
                last_entry_price = avgPrice
                last_exit_price = avgPrice + self.pips
                row.update({"status":'filled'})
                buy_counter = 0
            else:
                row.update({"status":'cancelled'})
                buy_counter += 1
                if buy_counter > self.max_buy_wait:
                    buy_counter = 0
                    low = position.low

            trades.append(row)     
            row = {}    

        return sum 

    def manage_alerts(self, position, buy_variation_dump, buy_variation_pump):
        if last_entry_price > 0 and position.open < (last_entry_price * (1- (buy_variation_dump/100))):          
            send_email(Mail_Subject.BUY_VAR_DUMP)
            exit()

        '''
        if last_exit_price > 0 and o < (last_exit_price * (1- (sell_variation_dump/100))):          
            send_email(Mail_Subject.SELL_VAR_DUMP)
            exit()            
        '''

        if last_entry_price > 0 and position.open > (last_entry_price * (1 + (buy_variation_pump/100))):          
            send_email(Mail_Subject.BUY_VAR_PUMP)
            exit()            

        '''
        if last_exit_price > 0 and o > (last_exit_price * (1 + (sell_variation_pump/100))):          
            send_email(Mail_Subject.SELL_VAR_PUMP)
            exit()            
        '''

    def switch_price_reference(self, ref, o, h, l, c):
        if ref == Reference.OPEN:
            e = o

        if ref == Reference.HIGH:
            e = h

        if ref == Reference.HLC2:
            e = (h + l + c) /2

        if ref == Reference.HLC3:
            e = (h + l + c) /3
            
        if ref == Reference.LOW:
            e = l

        if ref == Reference.HL:
            e = (h+l)/2

        if ref == Reference.OC2:
            e = (o+c)/2
        return e

    def entry_position(self, d, o, l, v, e):
        global buy_counter,last_entry_price,last_exit_price,sum,dataframe,low,row
        entry_price = e
        # if e == low:
        self.balance = self.get_balance('USDT')
        shares = (self.balance + sum) / e
        if not self.checkVolume or v >= shares:
            details = f"ACHAT a {o} sur la bougie du {d}"
            # dataframe.astype({"entry_price":float})
            
            def add_entry(e,d,shares):
                # '''
                # '''
                # shares = str(10)
                try:
                    result = session.place_order(category="spot",
                    symbol=self.instrument,
                    side="Buy",
                    orderType="Limit",
                    qty=self.round_down(shares,2),
                    price=l,
                    timeInForce="IOC",
                    # orderLinkId="spot-test-postonly",
                    isLeverage=0,
                    orderFilter="Order") 

                except Exception as e:
                    print(str(e))
                    print(e.__traceback__.tb_lineno)
                
                row.update({"details":details})
                row.update({"entry_price":e})
                row.update({"entry_date":d.strftime("%Y-%m-%d %H:%M:%S")})
                row.update({"exit_price":e+self.pips})
                row.update({"shares":shares})
                row.update({"type":"B"})
                
                return result
            try:
                result = add_entry(entry_price,d,shares)

            except Exception as e:
                print(str(e))
                print(e.__traceback__.tb_lineno)

            last_entry_price = l
            last_exit_price = l+self.pips
            return result
        else:
            row.update({"details":f"Pas assez de volume pour acheter"})
            buy_counter += 1

    def exit_position(self, position):
        global sell_counter,sum,last_entry_price,last_exit_price,row
        global low
        try:
            x = position.open if last_exit_price == 0 else last_exit_price
            last_exit_price = x
            d = position.date
            o = position.open
        except Exception as e:
            print(str(e))
            print(e.__traceback__.tb_lineno)

        # if o == x:
        s = position.get("shares")
        if not self.checkVolume or s<=self.avgVolume:
            def add_exit(o):
                try:
                    result = session.place_order(category="spot",
                    symbol=self.instrument,
                    side="Sell",
                    orderType="Limit",
                    qty=self.round_down(s,6),
                    price=x,
                    timeInForce="IOC",
                    isLeverage=0,
                    orderFilter="Order") 

                except Exception as e:
                    print(str(e))
                    print(e.__traceback__.tb_lineno)

                row.update({"details":f"VENTE a {x} sur la bougie du {d}"})
                row.update({"exit_date":d.strftime("%Y-%m-%d %H:%M:%S")})
                row.update({"exit_price":x})
                row.update({"shares":s})
                row.update({"type":"S"})
                row.update({"balance":sum})

                return result
            try:
                result = add_exit(o)
            except Exception as e:
                print(str(e))
                print(e.__traceback__.tb_lineno)
            
                    # if (earn < cost): print(balance+oldsum,balance+sum)

            low = position.low
            # sell_counter = 0
        else:
            # self.dataframe_add("details",f"Pas assez de volume pour vendre")
            sell_counter += 1

                # self.dataframe_add("exit_price",low)
                # self.dataframe_add("details",f"VENTE FORCE a {low}")            
            # else:
                # self.dataframe_add("type",f"N")
                # self.dataframe_add("entry_date",d)
                # self.dataframe_add("details",f"On passe bougie suivante")

        return result      

    def show(self,sum):
        print(self.balance + sum)
        print(self.avgVolume)
        print(str((sum/self.balance) * 100),'%')

    def dataframe_init(self):
        self.trades = TinyDB('trades.json')
        self.first_use_case_date = self.first_use_case_date.strftime('%Y-%m-%d %H:%M:%S')
        return pd.DataFrame(columns=["date","Open","High","Low","Close","Volume","entry_date","entry_price","exit_price","shares","type","exit_date","details","balance"])
        
        # return self.dataframe

    def dataframe_persist(self):
        global trades
        self.dataframe = pd.DataFrame(trades)
        self.dataframe.to_csv(f"Report[MAJ{self.runDate.strftime(DAY_FORMAT)}]_FILLED_2D.csv",decimal=',')

    def fill_position_from_array(self,position,arr):
        setattr(position,'date',arr[0])
        setattr(position,'entry_date',arr[6])
        setattr(position,'entry_price',arr[7])
        setattr(position,'exit_price',arr[8])
        setattr(position,'shares',arr[9])
        setattr(position,'type',arr[10])
        setattr(position,'exit_date',arr[11])
        setattr(position,'details',arr[12])
        return position
    
    def fill_position_from_series(self,position,serie):
        pos = self.fill_position_from_array(position,serie.array)
        return pos

    def round_down(self,f,n):
        s = str(f)
        if '.' in s:
            c = s.split('.')
            l = len(c[1])
            if l > n+1:
                d=c[1][:n+1]
                e = d[:-1] + "0"
                return float(c[0] + "." + e)
            else:
                return f


'''
s = Strategy(1000,1,30,30,Reference.OPEN,10,10,10,10)
sum = 0
sum = s.process()
s.dataframe_persist()
s.show(sum)
'''




# print(positions)
smtp_server = 'smtp.free.fr'
smtp_port = 587
smtp_username = 'ybmail@free.fr'
smtp_password = f"ethylene"

texts = {}

body = """
Bonjour,
Le dernier prix d'ouverture a subi une variation de moins de 10% par rapport au dernier prix connu .Ceci mérite peut-être votre attention
Le processus a été complètement stoppé le temps de l'analyse.
"""

texts['BUY_VAR_DUMP'] = {
    "subject":"DUMP ou KRACK en cours après achat",
    "body":body
}

body = """
        Bonjour,
            Le dernier prix d'ouverture est inférieur de 10% au prix du dernier vente.Ceci mérite peut-être votre attention
            Le processus a été complètement stoppé le temps de l'analyse.
        """

texts['SELL_VAR_DUMP'] = {
    "subject":"DUMP ou KRACK en cours après vente",
    "body":body
}


body = """
        Bonjour,
            Le dernier prix d'ouverture a subi une variation de plus de 10% par rapport au dernier prix connu.Ceci mérite peut-être votre attention
            Le processus a été complètement stoppé le temps de l'analyse.
        """

texts['BUY_VAR_PUMP'] = {
    "subject":"PUMP en cours après achat",
    "body":body
}

body = """
        Bonjour,
            Le dernier prix d'ouverture est supérieur de 10% au prix de la derniere vente.Ceci mérite peut-être votre attention
            Le processus a été complètement stoppé le temps de l'analyse.
        """

texts['SELL_VAR_PUMP'] = {
    "subject":"PUMP en cours après vente",
    "body":body
}

body = """
        Bonjour,
            Sur une des opérations le gain a été négatif.Ceci mérite peut-être votre attention
            Le processus a été complètement stoppé le temps de l'analyse.
        """
texts['NEGATIVE_GAIN'] = {
    "subject":"Gain négatif lors d'un trade",
    "body":body
}

recipients = ['bentaleb.youness@gmail.com']

msg = MIMEMultipart()
msg['From'] = smtp_username
msg['To'] = ",".join(recipients)

buy_counter = 0
sell_counter = 0
low = 0
last_entry_price = 0
last_exit_price = 0
sum = 0
dataframe = {}
session = {}
position = {}
row = {}
quote = "USDT"
instrument = base + quote
trades = []
DAY_FORMAT = "%Y-%m-%d"


#testnet
'''
testnet=True,
api_key="3KBEJYOE4NhdkTw2db",
api_secret="L2kGWggYMgh0mcHzaqc34Nz9cGvzwTuIrNnu",
'''


session = HTTP(
    #mainnet
    testnet=False,
    api_key=api_key,
    api_secret=api_secret,
)

eub = tz.gettz('Europe/Berlin')


server_time = session.get_server_time()["result"]["timeSecond"]
date_server_time = datetime.datetime.fromtimestamp(int(server_time))
delta = datetime.timedelta(minutes=-3)
low_time = date_server_time + delta

'''
line = session.get_kline(
    category="spot",
    symbol=instrument,
    interval=1,
    start=low_time.timestamp() * 1000,
)
'''
'''
testnet=True,
channel_type="spot",
api_key = "3KBEJYOE4NhdkTw2db",
api_secret="L2kGWggYMgh0mcHzaqc34Nz9cGvzwTuIrNnu"
'''



s = Strategy(1000,1,900,900,Reference.LOW,10,10,10,10,instrument)


def handle_message_bybit(message):
    handle_message(ws,message)

def handle_message_backtest(m):
    message = json.loads(m)
    handle_message(ws,message)

def handle_message(ws,message):
    websocket.dump("msg",message)
    d = datetime.datetime.fromtimestamp(message['data'][0]['start']/1000)
    o = float(message['data'][0]['open'])
    h = float(message['data'][0]['high'])
    l = float(message['data'][0]['low'])
    c = float(message['data'][0]['close'])
    v = float(message['data'][0]['volume'])
    row = {}
    position = Position(d,o,h,c,l,v)
    s.process(position)
    end = time.time() 
    # s.dataframe_persist()
    # s.show(sum)
    # print(message)

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

try:
    websocket.enableTrace(True)
    if (not DEBUG):
        ws = WebSocket(
        channel_type="spot",
        testnet=False,
        api_key="tOkx1lElyxcjnegbFw",
        api_secret="i9qYG3cVycnZCAWdBR0WVa6FcZlYvsnzpicP"
       )
        ws.kline_stream(
            interval=1,
            symbol=instrument,
            callback=handle_message_bybit
        )
    else:    
        ws = websocket.WebSocketApp("ws://localhost:8765", on_message=handle_message_backtest)
        ws.run_forever() 

except Exception as e:
    print(str(e))
    print(e.__traceback__.tb_lineno)

end = time.time()
begin = time.time()
elapsed = end-begin
while True:
# elapsed < MAX_RUNNING_TIME:
    time.sleep(1)
    if s.passage % 30 == 0 and len(trades) > 0:
        s.dataframe_persist()
    s.passage += 1
    end = time.time()
    elapsed = end-begin

print("finish")


 




