import asyncio
import datetime
import json
import time
import uuid
from numpy import size
import pandas as pd

from tinydb import Query, TinyDB
from queue import PriorityQueue
from Buy import Buy
from Mail_Subject import Mail_Subject

from Position import Position
from Reference import Reference
from Sell import Sell
from Trade import Trade
from mail import send_email
from termcolor import colored

pips = 1/10000
# take the low price
takeLow = False
api_key="tOkx1lElyxcjnegbFw",
api_secret="i9qYG3cVycnZCAWdBR0WVa6FcZlYvsnzpicP",
# compte trading
api_key = "WMQ7ZAe2DIQNMjPoSE"
api_secret = "Qe7lJGokH8OPphTI2EHkR54RXkOkPMIp1C4F"
# Fin
FILLED = 'Filled'
UNFILLED = 'Unfilled'
MIN_SHARES_REQUIRED = 9
MAX_RUNNING_TIME = 300
MIN_AS_SECOND = 60
MODE = 0 # 0 for aggressive (entry price selling), 1 for cool mode (entry price minored 1 pips), 2 for middle (low price selling)


color = "white"
checkElapsedOrder = False
buy_counter = 0
sell_counter = 0
low = 0
last_entry_price = 0
last_exit_price = 0
sum = 0
dataframe = {}
position = {}
row = {}
session = {}
DAY_FORMAT = "%Y-%m-%d"
quantity = 0
sl = None

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
    def __init__(self,b,q,msw,mbw,r,svd,bvd,svp,bvp,base,quote,session):
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
        self.base = base
        self.quote = quote
        self.instrument = base + quote
        self.max_try_to_sell = msw * MIN_AS_SECOND
        self.max_try_to_buy = mbw * MIN_AS_SECOND
        self.trades = []
        self.max_wait_sell = 1
        self.max_wait_buy = 1
        self.position = {}
        self.runDate = datetime.datetime.now()
        self.avgVolume = 0
        self.df_trades = self.persistence_init()
        self.session = session
        self.clean_trades()
        self.done = False
        self.trade = {}

    def get_balance(self,token):
        try:            
            assets = self.session.get_coin_balance(
            accountType="UNIFIED",
            coin=token,
            )
            return float(assets['result']['balance']['walletBalance'])

        except Exception as ex:
            print(colored('@ERROR@','light_red'))
            print("     " +  str(ex))
            print("     " +str(ex.__traceback__.tb_lineno))
            print("     " +str(ex.__traceback__.tb_lasti))

    def get_transfer_balance(self,token):
        try:            
            assets = self.session.get_coin_balance(
            accountType="UNIFIED",
            coin=token,
            )
            return float(assets['result']['balance']['transferBalance'])
        except Exception as ex:
            print(colored('@ERROR@','light_red'))
            print("     " +  str(ex))
            print("     " +str(ex.__traceback__.tb_lineno))
            print("     " +str(ex.__traceback__.tb_lasti))

    def get_wallet_balance(self):
        try:
            balance = self.session.get_wallet_balance(accountType="UNIFIED")
            self.balance = balance["totalEquity"]
            return balance
        except Exception as ex:
            print(colored('@ERROR@','light_red'))
            print("     " +  str(ex))
            print("     " +str(ex.__traceback__.tb_lineno))
            print("     " +str(ex.__traceback__.tb_lasti))

    def manage_status(self,orderId):
        try:
            status = ''
            order = self.session.get_executions(
                category="spot",
                limit=1,                        
                orderId=orderId,
                symbol=self.instrument,
                orderStatus="Filled"

            )
            if len(order['result']['list']) == 0:
                status = 'Unfilled'

            return status
        
        except Exception as ex:
            print(colored('@ERROR@','light_red'))
            print("     " +  str(ex))
            print("     " +str(ex.__traceback__.tb_lineno))
            print("     " +str(ex.__traceback__.tb_lasti))

    def cancel_order(self,orderId):
        global row
        isCanceled = False
        while not isCanceled:   # on boucle jusqu'a annuler l'ordre
            orderResult = self.session.cancel_order(
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
        global entry_price,exit_price
        try:
            orderId = orderResult['result']['orderId']
            status = self.manage_status(orderId)
            timeout = 0
            if status == "Filled": # l'ordre n'est pas rempli
                if (not isIOT):# si on attends une annulation d'ordre
                    max_wait = self.max_wait_sell if orderResult['result']['side'] == 'Sell' else self.max_wait_buy
                    while (timeout <= (self.max_wait * MIN_AS_SECOND)): # tant qu'on doit boucler
                        time.sleep(1)
                        timeout += 1
                        status = self.manage_status(orderId)
                        if (status == FILLED):
                            break
                
                if status != FILLED or isIOT:
                    self.cancel_order(orderId)

                
            return [status,orderId]
        
        except Exception as ex:
            print(colored('@ERROR@','light_red'))
            print("     " +  str(ex))
            print("     " +str(ex.__traceback__.tb_lineno))
            print("     " +str(ex.__traceback__.tb_lasti))

    def manage_filled_entry(self,id):
        global position,entry_price,exit_price
        try:
            order = self.session.get_executions(
                category="spot",
                limit=1,                        
                orderId=id,
                symbol=self.instrument,
                orderStatus=FILLED
            )

            if len(order['result']['list']) == 0:
                return order
            
            print(f"get order with {id}, {self.instrument}")
            stats = order['result']['list'][0]

            avgPrice = stats['execPrice']
            quantity = float(stats['execQty'])
            self.valid_entry(id)

            if avgPrice != "":
                avgPrice = float(avgPrice)
                entry_price = avgPrice
                exit_price = avgPrice + self.pips

            return order

        except Exception as ex:
            print(colored('@ERROR@','light_red'))
            print("     " +  str(ex))
            print("     " +str(ex.__traceback__.tb_lineno))
            print("     " +str(ex.__traceback__.tb_lasti))

    def manage_filled_exit(self,id):
        global position,entry_price,exit_price
        try:
            order = self.session.get_executions(
                category="spot",
                limit=1,                        
                orderId=id,
                symbol=self.instrument,
                orderStatus=FILLED
            )

            if len(order['result']['list']) == 0:
                return order
                
            print(f"get order with {id}, {self.instrument}")
            stats = order['result']['list'][0]

            avgPrice = stats['execPrice']
            quantity = float(stats['execQty'])
            self.valid_exit(id)

            if avgPrice != "":
                avgPrice = float(avgPrice)
                entry_price = avgPrice
                exit_price = avgPrice + self.pips
            
            return order
        
        except Exception as ex:
            print(colored('@ERROR@','light_red'))
            print("     " +  str(ex))
            print("     " +str(ex.__traceback__.tb_lineno))
            print("     " +str(ex.__traceback__.tb_lasti))

    def clean_trades(self):
        Trade = Query()
        entries = self.js_trades.search(Trade.type == "B" and Trade.status == FILLED)
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


    def read_last_candle(self):
        df = pd.read_json('ohlcv.json')
        if size(df) == 0:
            return None
        j = df.iloc[-1].to_json()
        # j = ohlcv.to_json()
        s = json.loads(j)['_default']
        return s

    def parse_position(self,s):
        position = Position( datetime.datetime.fromtimestamp(s['start']/1000),float(s['open']),float(s['high']),float(s['low']),float(s['close']),float(s['volume']))
        return position

    def get_last_position(self):
        global last_entry_price,last_exit_price
        position = {}
        try:
            s = self.read_last_candle()
            
            if s is not None:
                position = self.parse_position(s)
                position.entry_price = round(last_entry_price,4)
                position.exit_price = round(last_exit_price,4)
                self.position = position

                return position
            
        except Exception as ex:
            print(colored('@ERROR@','light_red'))
            exception = str(ex)
            print("     " +  exception)
            print("     " +str(ex.__traceback__.tb_lineno))
            print("     " +str(ex.__traceback__.tb_lasti))
            if 'Trailing' in exception:
                return None
            else:
                exit()


    def new_process(self):
        global quantity,exit_price,entry_price,color
        sellmanager = Sell()
        buymanager = Buy()
        sellmanager.trade = self.trade
        buymanager.trade = self.trade

        buymanager = Buy()
        
        try:
            order = None
            orders = self.session.get_executions(
                category="spot",
                limit=1, 
                orderStatus="Filled",
            )
            last_order_executed_side = 'Buy'
            last_order_executed = {}

            if len(orders['result']['list']) > 0:
                last_order_executed = orders['result']['list'][0]                
                last_order_executed_side = last_order_executed['side']
          

            if last_order_executed_side == 'Buy':
                print(colored('La dernière transaction est un achat, on vends','blue'))
                print(colored(' on teste si on a pas déja un ordre en corus de vente','blue'))
                orders = self.session.get_open_orders(
                category="spot",
                limit=1,                        
                symbol=self.instrument,
                side = 'Sell'
                )

                if len(orders['result']['list']) > 0:
                    order = orders['result']['list'][0]
                # if order['price'] != '0':
                    print(colored(' Oui? on test si il est expiré ','blue'))
                    [passed,elapsed] = self.checkElapsedOrder(order,'Sell')
                    if elapsed:
                        print(colored(' il est expire on le mets a jour ','blue'))
                        
                        entry_price = float(last_order_executed['execPrice'])
                        self.trade.entry_price = entry_price

                        exit_price = float(order['price'])
                        self.trade.exit_price = exit_price

                        self.update_sell_price()
                        self.amend_sell(order)
                    else:
                        print(colored(passed,"light_blue"))

                else:
                    print(colored(' Non? on crée un ordre de vente ','blue'))
                    entry_price = float(last_order_executed['execPrice'])
                    exit_price = entry_price + self.pips
                    quantity = self.round_down(self.get_balance(self.base) / exit_price,2)
                    
                    self.trade.entry_price = entry_price
                    self.trade.exit_price = exit_price

                    self.sell(exit_price)
                    # self.report_filled_trade()
                    
            else:
                print(colored('La dernière transaction est une vente, on achète','blue'))
                print(colored(' on teste si on a pas déja un ordre en corus d''achat','blue'))
                orders = self.session.get_open_orders(
                category="spot",
                limit=1,                        
                symbol=self.instrument,
                side = 'Buy'
                )
                if len(orders['result']['list']) > 0:
                    order = orders['result']['list'][0]
                    print(colored(' Oui? on test si ce il est expiré ','blue'))
                    [passed,elapsed] = self.checkElapsedOrder(order,'Buy')
                    if elapsed:
                        print(colored(' il est expire on le mets a jour ','blue'))
                        entry_price = self.update_buy_price()
                        self.amend_buy(order)
                    else:
                        print(colored(passed,'light_cyan'))
                else:
                    print(colored(' Non? on crée un ordre pour acheter ','blue'))
                    self.buy()
                    # self.report_filled_trade()

        except Exception as ex:
            print(colored('@ERROR@','light_red'))
            print("     " +  str(ex))
            print("     " +str(ex.__traceback__.tb_lineno))
            print("     " +str(ex.__traceback__.tb_lasti))

    def sell(self,exit_price):
        global color
        try:
            print(colored("cas de vente","blue"))
            print(colored(f"Exit position at {exit_price}",color))
            [status,order] = self.exit_position()
            if order is not None and 'result' in order:
                last_order_id = order['result']['orderId']

        except Exception as ex:
            print(colored('@ERROR@','light_red'))
            print("     " +  str(ex))
            print("     " +str(ex.__traceback__.tb_lineno))
            print("     " +str(ex.__traceback__.tb_lasti))

    def buy(self):
        global entry_price,position,quantity
        print(colored("cas d'achat","blue"))
        print(colored("Aucun ordre en cours d'achat, création..","blue"))
        print(colored("On rentre au prix de référence","blue"))
        position = self.get_last_position()    
        entry_price = self.switch_price_reference(self.ref)
        quantity = self.round_down(self.get_balance(self.quote) / entry_price,2)
        self.position = position
        position.entry_price = entry_price
        position.exit_price = position.entry_price + self.pips
        print(colored(f"    Enter position at {position.entry_price}",color))
        [status,order] = self.entry_position()
        if order is not None and 'result' in order:
            last_order_id = order['result']['orderId']

    def amend_buy(self,order):
        global entry_price
        self.amend_order(entry_price,order,'buy')

    def amend_sell(self,order):
        global exit_price
        self.amend_order(exit_price,order,'sell')

    def amend_order(self,price,order,side):
        global sl
        try:
            orderId = order['orderId']
            instrument = self.quote if side == 'buy' else self.base
            quantity = self.round_down(self.get_balance(instrument) / price,2)
            if float(order['price']) != price:
                res = self.session.amend_order(orderId = orderId,category="spot",symbol=self.instrument,price=price,qty=quantity)
            else:
                res = self.session.amend_order(orderId = orderId,category="spot",symbol=self.instrument,price=1.0104,qty=quantity)
                while float(res['retCode']) != 0:
                    time.sleep(1/1000)
                res = self.session.amend_order(orderId = orderId,category="spot",symbol=self.instrument,price=price,qty=quantity)

            while float(res['retCode']) != 0:
                time.sleep(1/1000)

        except Exception as ex:
            print(colored('@ERROR@','light_red'))
            print("     " +  str(ex))
            print(order + " vs " + price)
            print("     " +str(ex.__traceback__.tb_lineno))
            print("     " +str(ex.__traceback__.tb_lasti))
        
    def update_sell_price(self):
        global color,entry_price,exit_price,MODE
        print(colored("Elapsed time...need to amend order",color))
        if MODE == 0:
            exit_price = round(entry_price,4)
            print(colored(f' Try to sell bought price : {exit_price}',color))
            MODE = 1
        elif MODE == 1:
            exit_price = round(entry_price-self.pips,4)
            print(colored(f' Try to sell bought price minus 1 pips: {exit_price}',color))
            MODE = 2
        elif MODE == 2:
            sell_position = self.get_last_position()
            exit_price = round(sell_position.low,4)
            print(colored(f' Bought price too expensive. Go out! :  {exit_price}',color))
        return exit_price

    def update_buy_price(self):        
        global color,last_entry_price
        print(colored("Elapsed time...need to amend order",color))
        position = self.get_last_position()
        low = position.low
        open = position.open
        last_entry_price = open
        # if MODE == 0 else last_entry_price+self.pips
        return last_entry_price

    def checkElapsedOrder(self,order,side):
        created = datetime.datetime.fromtimestamp(int(order['updatedTime'])/1000)
        now = datetime.datetime.now()
        elapsed = now - created
        max_wait = self.max_wait_buy if side == 'Buy' else self.max_wait_sell
        return [elapsed,(elapsed > datetime.timedelta(seconds=max_wait * MIN_AS_SECOND))]


    def process(self):
        global MODE,color
        self.done = False
        self.trade = Trade()   
        while True:
            if not self.done:
                color = self.trade.getTradeLevel()
                print(colored('Process on last candle...',color))        
                self.new_process()
                time.sleep(2)
                continue


            else:
                time.sleep(2)
                self.done = False

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

    def switch_price_reference(self, ref):
        position = self.position
        o = position.open
        h = position.high
        l = position.low
        c = position.close

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

    def entry_position(self):
        global quantity,entry_price,position,exit_price
        if not self.checkVolume or position.volume >= quantity:
            status = ''
            orderId = ''
            try:
                order = self.add_entry()
                orderId = order['result']['orderId']
                # status = order['result']['orderStatus']
                '''
                if order is not None:
                    [status,orderId] = self.manage_order(order)
            
                if status == FILLED:
                    order = self.manage_filled_entry(orderId)
                '''
            except Exception as ex:
                print(colored('@ERROR@','light_red'))
                print("     " +  str(ex))
                print("     " +str(ex.__traceback__.tb_lineno))
                print("     " +str(ex.__traceback__.tb_lasti))

            exit_price = entry_price+self.pips
            return [status,orderId]
        
        else:
            buy_counter += 1
            
        return ['','']

    def add_entry(self):
        global position,quantity,entry_price
        try:
            price = entry_price
            result = self.session.place_order(category="spot",
            symbol=self.instrument,
            side="Buy",
            orderType="Limit",
            qty=self.round_down(quantity,2),
            price=self.round_down(price,6),
            timeInForce="GTC",
            # orderLinkId="spot-test-postonly",
            isLeverage=0,
            orderFilter="Order") 
            
            return result

        except Exception as ex:
            print(colored('@ERROR@','light_red'))
            print("     " +  str(ex))
            print("     " +str(ex.__traceback__.tb_lineno))
            print("     " +str(ex.__traceback__.tb_lasti))

    def valid_entry(self,id):
        position = self.position
        row = {}
        row.update({"details":f"Achat a {position.entry_price} sur la bougie du {position.date}"})
        row.update({"open":position.open})
        row.update({"high":position.high})
        row.update({"low":position.low})
        row.update({"close":position.close})
        row.update({"entry_price":position.entry_price})
        row.update({"entry_date":position.date.strftime("%Y-%m-%d %H:%M:%S")})
        row.update({"exit_price":position.entry_price+self.pips})
        row.update({"shares":position.shares})
        row.update({"type":"B"})
        row.update({"status":"Filled"})
        row.update({"orderId":id})
        self.trade = row
        return row

    def add_exit(self):
        global quantity,exit_price  
        result = {}
        try:
            price = exit_price
            result = self.session.place_order(category="spot",
            symbol=self.instrument,
            side="Sell",
            orderType="Limit",
            qty=self.round_down(quantity,6),
            price=self.round_down(price,4),
            timeInForce="GTC",
            isLeverage=0,
            orderFilter="Order") 
            return result

        except Exception as ex:
            print(colored('@ERROR@','light_red'))
            print("     " +  str(ex))
            print("     " +str(ex.__traceback__.tb_lineno))
            print("     " +str(ex.__traceback__.tb_lasti))

    def exit_position(self):
        global quantity,exit_price,entry_price
        try:
            status = ''
            orderId = ''
            if not self.checkVolume or quantity <= self.avgVolume:
                order = self.add_exit()
                if order is not None:
                    [status,orderId] = self.manage_order(order)
                
                if status == "Filled":
                    order = self.manage_filled_exit(orderId)

                return [status,order]      
                
        except Exception as ex:
            print(colored('@ERROR@','light_red'))
            print("     " +  str(ex))
            print("     " +str(ex.__traceback__.tb_lineno))
            print("     " +str(ex.__traceback__.tb_lasti))
            

    def valid_exit(self,id):
        position = self.position
        row = {}
        row.update({"details":f"VENTE a {position.exit_price} sur la bougie du {position.date}"})
        row.update({"open":position.open})
        row.update({"high":position.high})
        row.update({"low":position.low})
        row.update({"close":position.close})
        row.update({"exit_date":position.date.strftime("%Y-%m-%d %H:%M:%S")})
        row.update({"entry_price":position.entry_price})
        row.update({"exit_price":position.exit_price})
        row.update({"shares":position.shares})
        row.update({"type":"S"})
        row.update({"balance":sum})
        row.update({"status":"Filled"})
        row.update({"orderId":id})
        self.trade = row

    def report_filled_trade(self):
        trade = self.trade
        self.js_trades.insert(trade)        
        self.trades.append(trade)     
        self.trades_persist()

    def show(self,sum):
        print((self.balance + sum))
        print((self.avgVolume))
        print((str((sum/self.balance) * 100),'%'))

    def persistence_init(self):
        self.js_trades = TinyDB('trades.json')
        self.ohlcv = TinyDB('ohlcv.json')
        self.first_use_case_date = self.first_use_case_date.strftime('%Y-%m-%d %H:%M:%S')
        return pd.DataFrame(columns=["date","Open","High","Low","Close","Volume","entry_date","entry_price","exit_price","shares","type","exit_date","details","balance"])
        
        # return self.dataframe

    def trades_persist(self):
        self.df_trades = pd.DataFrame(self.trades)
        self.df_trades.to_csv(f"Report.csv",decimal=',')        


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

