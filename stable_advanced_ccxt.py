#!/usr/bin/env python
# -*- coding: utf-8 -*- 
import datetime
import json
import math
from tinydb import TinyDB, Query
import time
import pandas as pd
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import sys
from dateutil import tz 
root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(root + '/python')
sys.path.append(sys.path[0] + '/class')
import websocket
from pybit.unified_trading import HTTP,WebSocket
from Mail_Subject import Mail_Subject
from Reference import Reference
from Position import Position
from Timer import Timer
import threading

# A editer
# compte principal
takeLow = False
api_key="tOkx1lElyxcjnegbFw",
api_secret="i9qYG3cVycnZCAWdBR0WVa6FcZlYvsnzpicP",
# compte trading
api_key = "WMQ7ZAe2DIQNMjPoSE"
api_secret = "Qe7lJGokH8OPphTI2EHkR54RXkOkPMIp1C4F"
base = "USDC"
pips = 1/10000
MIN_SHARES_REQUIRED = 9
MAX_RUNNING_TIME = 300
MIN_AS_SECOND = 60
DEBUG = not True
MODE = 0 # 1 for cool mode (low price selling), 0 for aggressive (entry price selling)
# Fin
ohlcv = pd.DataFrame(columns=["date","Open","High","Low","Close","Volume"])


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
        print(f"{mail_subject.name} - E-mail envoyé avec succès.")
    except Exception as e:
        print(('Erreur lors de l\'envoi de l\'e-mail :', str(e)))
        print(str(e.__traceback__.tb_lineno))

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
        self.max_try_to_sell = msw
        self.max_try_to_buy = mbw
        
        self.max_wait_sell = 30
        self.max_wait_buy = 30

        self.runDate = datetime.datetime.now()
        self.avgVolume = 0
        self.df_trades = self.persistence_init()
        self.clean_trades()


    def get_balance(self,token):
        global session
        try:            
            assets = session.get_coin_balance(
            accountType="UNIFIED",
            coin=token,
            )
            return float(assets['result']['balance']['walletBalance'])
        except Exception as e:
            print((str(e)))

    def get_wallet_balance(self):
        global session
        try:
            balance = session.get_wallet_balance(accountType="UNIFIED")
            self.balance = balance["totalEquity"]
            return balance
        except Exception as e:
            print((str(e)))


    def manage_status(self,orderResult):
        orderId = orderResult['result']['orderId']
        order = session.get_order_history(
            category="spot",
            limit=1,                        
            orderId=orderId,
            symbol=self.instrument
        )
        stats = order['result']['list'][0]
        status = stats['orderStatus']
        return status

    def cancel_order(self,orderId):
        global row
        isCanceled = False
        while not isCanceled:   # on boucle jusqu'a annuler l'ordre
            orderResult = session.cancel_order(
                category="spot",
                orderId=orderId,
                symbol=self.instrument
            )
            isCanceled = True
            status = orderResult["retCode"]
            if status == 0:
                status = 'Cancelled'
                isCanceled = True
    
        if isCanceled:
            row.update({'status':status})        

    def manage_order(self,orderResult,isIOT = False):
        global last_entry_price,last_exit_price,row
        try:
            orderId = orderResult['result']['orderId']
            status = self.manage_status(orderResult)
            isFilled = status == 'Filled'
            isCanceled = False
            timeout = 0
            if not isFilled: # l'ordre n'est pas rempli
                if (not isIOT):# si on attends une annulation d'ordre
                    while (timeout <= (self.max_wait_buy * MIN_AS_SECOND)): # tant qu'on doit boucler
                        time.sleep(1)
                        timeout += 1
                        status = self.manage_status(orderResult)
                        if (status == 'Filled'):
                            break
                
                if status != 'Filled' or isIOT:
                    self.cancel_order(orderId)

            if status == 'Filled':
                order = session.get_order_history(
                    category="spot",
                    limit=1,                        
                    orderId=orderId,
                    symbol=self.instrument
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
                    row.update({"status":'Filled'})
                    row.update({"shares":shares})
                
            return [row['status'],orderId]
        
        except Exception as ex:
                print((str(ex)))
                print(str(ex.__traceback__.tb_lineno))

    def clean_trades(self):
        Trade = Query()
        entries = self.js_trades.search(Trade.type == "B" and Trade.status == 'Filled')
        removed_docs_id = []
        kept_docs = []
        removed_docs = []
        if len(entries) > 0:
            entry = entries[0]
            doc_id = entry.doc_id+1
            exit = self.js_trades.get(doc_id=doc_id)
            kept_docs.append(entry.doc_id)
            kept_docs.append(exit.doc_id)        
            for e in self.js_trades:
                if e.doc_id not in kept_docs:
                    self.js_trades.remove(doc_ids = [e.doc_id])
            return exit
        

    def process(self,position):
        try:
            global last_entry_price,last_exit_price,low,sum,dataframe,session,row,trades,buy_counter,sell_counter,entry_price
            # dataframe = self.dataframe_init()
            ref = self.ref
            buy_variation_dump = self.buy_variation_dump
            buy_variation_pump = self.buy_variation_pump

            entry_price = 0

            entry_price = self.switch_price_reference(ref, position.open, position.high, position.low, position.close)
            

            if takeLow:
                entry_price -= self.pips

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
                    all = self.js_trades.search(Trade.type == "B")
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
                    filtered = [x for x in orders['result']['list'] if x["side"] == "Buy"]
                    l = list(filtered)
                    stats = {"avgPrice":"","symbol":instrument}
                    if (len(l) > 0):
                        stats = l[0]                 
                    

                    if stats['symbol'] == instrument:                        
                        avgPrice = stats['avgPrice']
                        shares = float(stats['qty'])
                        # status = stats['orderStatus']
                        if avgPrice not in ("",0,'0'):
                            avgPrice = float(avgPrice)
                            # insert last buy trade in db
                            row.update({"details":"dernier achat récupéré via api"})
                            row.update({"open":position.open})
                            row.update({"high":position.high})
                            row.update({"low":position.low})
                            row.update({"close":position.close})
                            row.update({"entry_price":entry_price})
                            row.update({"entry_date":position.date.strftime("%Y-%m-%d %H:%M:%S")})
                            row.update({"exit_price":entry_price+self.pips})
                            row.update({"shares":shares})
                            row.update({"type":"B"})
                            row.update({"status":"Filled"})
                            self.js_trades.insert(row)
                        else:
                            avgPrice = position.low if MODE == 1 else position.open
                        last_entry_price = avgPrice
                        if last_exit_price == 0:
                            last_exit_price = avgPrice + self.pips
                else:
                    last_exit_price = last_entry_price+self.pips

                [status,orderId] = self.exit_position( position)
                
                if status == 'Filled':
                    shares = row['shares']
                    sell_counter = 0
                    cost = last_entry_price*shares                
                    earn = last_exit_price*shares
                    sum += earn - cost
                    if sum < -10:
                        send_email(Mail_Subject.NEGATIVE_GAIN)
                        exit()
                else:
                    sell_counter += 1
                    if sell_counter > self.max_try_to_sell:
                        sell_counter = 0
                        low = position.low
                        last_exit_price = low if MODE == 1 else last_entry_price
                        last_entry_price = last_exit_price-self.pips


                self.js_trades.insert(row)        
                trades.append(row) 
                row = {}  

            else:        
                [status,orderId] = self.entry_position( position)
                isFilled = status == 'Filled'
                if isFilled:
                    order = session.get_order_history(
                        category="spot",
                        limit=1,                        
                        orderId=orderId,
                        symbol=self.instrument
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
                    row.update({"status":'Cancelled'})
                    buy_counter += 1
                    if buy_counter > self.max_try_to_buy:
                        buy_counter = 0
                        low = position.low

                trades.append(row)     
                row = {}    

            return sum 
        except Exception as ex:
            print(str(ex))
            print(str(ex.__traceback__.tb_lineno))

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

    def entry_position(self, position):
        global buy_counter,last_entry_price,last_exit_price,sum,dataframe,low,row,entry_price
        self.balance = self.get_balance('USDT')
        shares = (self.balance + sum) / entry_price
        if not self.checkVolume or position.volume >= shares:
            details = f"ACHAT a {position.open} sur la bougie du {position.date}"
            result = {}
            def add_entry(e,d,shares):
                try:
                    result = session.place_order(category="spot",
                    symbol=self.instrument,
                    side="Buy",
                    orderType="Limit",
                    qty=self.round_down(shares,2),
                    price=entry_price,
                    timeInForce="GTC",
                    # orderLinkId="spot-test-postonly",
                    isLeverage=0,
                    orderFilter="Order") 

                except Exception as ex:
                    print((str(ex)))
                    print(str(ex.__traceback__.tb_lineno))
                
                row.update({"details":details})
                row.update({"open":position.open})
                row.update({"high":position.high})
                row.update({"low":position.low})
                row.update({"close":position.close})
                row.update({"entry_price":entry_price})
                row.update({"entry_date":d.strftime("%Y-%m-%d %H:%M:%S")})
                row.update({"exit_price":entry_price+self.pips})
                row.update({"shares":shares})
                row.update({"type":"B"})
                
                return result
            try:
                result = add_entry(entry_price,position.date,shares)
                [status,orderId] = self.manage_order(result)

            except Exception as ex:
                print((str(ex)))
                print(str(ex.__traceback__.tb_lineno))

            last_entry_price = position.low
            last_exit_price = position.low+self.pips
            return [status,orderId]
        else:
            row.update({"details":f"Pas assez de volume pour acheter"})
            buy_counter += 1
            return ['','']

    def exit_position(self, position):
        global sell_counter,sum,last_entry_price,last_exit_price,row
        global low
        try:
            x = position.open if last_exit_price == 0 else last_exit_price
            last_exit_price = x
            d = position.date
            o = position.open
        except Exception as e:
            print((str(e)))
            print(str(e.__traceback__.tb_lineno))

        # if o == x:
        s = position.get("shares")
        if not self.checkVolume or s<=self.avgVolume:
            def add_exit(o):
                result = {}
                try:
                    result = session.place_order(category="spot",
                    symbol=self.instrument,
                    side="Sell",
                    orderType="Limit",
                    qty=self.round_down(s,6),
                    price=x,
                    timeInForce="GTC",
                    isLeverage=0,
                    orderFilter="Order") 

                except Exception as e:
                    print((str(e)))
                    print(str(e.__traceback__.tb_lineno))


                row.update({"details":f"VENTE a {x} sur la bougie du {d}"})
                row.update({"open":position.open})
                row.update({"high":position.high})
                row.update({"low":position.low})
                row.update({"close":position.close})
                row.update({"exit_date":d.strftime("%Y-%m-%d %H:%M:%S")})
                row.update({"exit_price":x})
                row.update({"shares":s})
                row.update({"type":"S"})
                row.update({"balance":sum})

                

                return result
            try:
                result = add_exit(o)
                [status,orderId] = self.manage_order(result)

            except Exception as e:
                print((str(e)))
                print(str(e.__traceback__.tb_lineno))
            
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

        return [status,orderId]      

    def show(self,sum):
        print((self.balance + sum))
        print((self.avgVolume))
        print((str((sum/self.balance) * 100),'%'))

    def persistence_init(self):
        self.js_trades = TinyDB('trades.json')
        self.first_use_case_date = self.first_use_case_date.strftime('%Y-%m-%d %H:%M:%S')
        return pd.DataFrame(columns=["date","Open","High","Low","Close","Volume","entry_date","entry_price","exit_price","shares","type","exit_date","details","balance"])
        
        # return self.dataframe

    def trades_persist(self):
        global trades
        self.df_trades = pd.DataFrame(trades)
        self.df_trades.to_csv(f"Report[MAJ{self.runDate.strftime(DAY_FORMAT)}]_FILLED_2D.csv",decimal=',')        


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
            if l >= n+1:
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
    start=low_time.timestamp() * 1000
)
'''
'''
testnet=True,
channel_type="spot",
api_key = "3KBEJYOE4NhdkTw2db",
api_secret="L2kGWggYMgh0mcHzaqc34Nz9cGvzwTuIrNnu"
'''



s = Strategy(1000,1,30,30,Reference.OPEN,10,10,10,10,instrument)
timer = Timer()


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
    ohlcv[-1] = [d,o,h,l,c,v]    
    position = Position(d,o,h,c,l,v)
    s.process(position)
    end = time.time() 
    time.sleep(20)
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

def run_kline():
    ws.kline_stream(
            interval=1,
            symbol=instrument,
            callback=handle_message_bybit)

try:
    websocket.enableTrace(True)
    if (not DEBUG):
        ws = WebSocket(
        channel_type="spot",
        testnet=False,
        api_key="tOkx1lElyxcjnegbFw",
        api_secret="i9qYG3cVycnZCAWdBR0WVa6FcZlYvsnzpicP",

       )
        run_kline()
    else:    
        ws = websocket.WebSocketApp("ws://localhost:8765", on_message=handle_message_backtest)
        ws.run_forever() 


except Exception as e:
    print((str(e)))
    print(str(e.__traceback__.tb_lineno))

end = time.time()
begin = time.time()
elapsed = end-begin
while True:
# elapsed < MAX_RUNNING_TIME:
    time.sleep(1)
    if s.passage % 30 == 0 and len(trades) > 0:
        s.trades_persist()
    s.passage += 1
    end = time.time()
    elapsed = end-begin

print("finish")


 




