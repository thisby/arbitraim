import asyncio
import datetime
import json
import time
from numpy import size
import pandas as pd

from tinydb import Query, TinyDB
from queue import PriorityQueue
from Mail_Subject import Mail_Subject

from Position import Position
from Reference import Reference
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
MIN_SHARES_REQUIRED = 9
MAX_RUNNING_TIME = 300
MIN_AS_SECOND = 60
MODE = 0 # 0 for aggressive (entry price selling), 1 for cool mode (entry price minored 1 pips), 2 for middle (low price selling)
# Fin

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
        self.max_wait_sell = 30
        self.max_wait_buy = 15

        self.runDate = datetime.datetime.now()
        self.avgVolume = 0
        self.df_trades = self.persistence_init()
        self.session = session
        self.clean_trades()
        self.done = False

    def get_balance(self,token):
        try:            
            assets = self.session.get_coin_balance(
            accountType="UNIFIED",
            coin=token,
            )
            return float(assets['result']['balance']['walletBalance'])
        except Exception as e:
            print((str(e)))

    def get_transfer_balance(self,token):
        try:            
            assets = self.session.get_coin_balance(
            accountType="UNIFIED",
            coin=token,
            )
            return float(assets['result']['balance']['transferBalance'])
        except Exception as e:
            print((str(e)))

    def get_wallet_balance(self):
        try:
            balance = self.session.get_wallet_balance(accountType="UNIFIED")
            self.balance = balance["totalEquity"]
            return balance
        except Exception as e:
            print((str(e)))

    def manage_status(self,orderResult):
        orderId = orderResult['result']['orderId']
        order = self.session.get_order_history(
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
        global last_entry_price,last_exit_price,row
        try:
            orderId = orderResult['result']['orderId']
            status = self.manage_status(orderResult)
            isFilled = status in ('Filled','New')
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

            if isFilled:
                order = self.session.get_open_orders(
                    category="spot",
                    limit=1,                        
                    orderId=orderId,
                    symbol=self.instrument
                )
                print(f"get order with {orderId}, {self.instrument}")
                stats = order['result']['list'][0]

                avgPrice = stats['price']
                status = 'Filled'
                row.update({"status":status})
                shares = float(stats['qty'])
                row.update({"orderId":orderId})

                if avgPrice != "":
                    avgPrice = float(avgPrice)
                    last_entry_price = avgPrice
                    last_exit_price = avgPrice + self.pips
                    row.update({"status":'Filled'})
                    row.update({"shares":shares})
                
            return [row['status'],orderId]
        
        except Exception as ex:
                print((str(ex)))
                print(str(ex.__traceback__.tb_lineno))
                print(str(ex.__traceback__.tb_lasti))

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
        

    def process(self):
        global MODE
        last_exit_price = 0
        last_entry_price = 0
        status = ""
        ohlcv = None
        # take the last price in db
        self.done = False
        persistType = 'json'
        while True:
            if not self.done:
                color = ""
                if MODE == 0:
                    color = "light_green"
                elif MODE == 1:
                    color = "light_yellow"
                else:
                    color = "red"

                print(colored('Process on last candle...',color))
                
                if persistType == 'json':
                    try:
                        df = pd.read_json('ohlcv.json')
                        if size(df) == 0:
                            continue
                        j = df.iloc[-1].to_json()
                        # j = ohlcv.to_json()
                        s = json.loads(j)['_default']
                    except Exception as eX:
                        exception = f"{eX.__traceback__.tb_lineno} {eX}"
                        print(colored(exception,color))
                        if 'Trailing' in exception:
                            continue
                        else:
                            exit()

                    position = Position( datetime.datetime.fromtimestamp(s['start']/1000),float(s['open']),float(s['high']),float(s['low']),float(s['close']),float(s['volume']))
                    position.entry_price = last_entry_price
                    position.exit_price = last_exit_price

                elif persistType == "queue":
                    # s = queue.get()
                    position = Position(float(s[0]),float(s[1]),float(s[2]),float(s[3]),float(s[4]),float(s[5]))
                elif persistType == "tinyDB":
                    # self.ohlcv = TinyDB('ohlcv.json')
                    all = self.ohlcv.all()
                    if status == 'Filled' or ohlcv == None:
                        ohlcv = all[-1]
                    self.ohlcv.truncate()
                    position = Position(datetime.datetime.fromtimestamp(ohlcv['start']/1000),float(ohlcv['open']),float(ohlcv['high']),float(ohlcv['low']),float(ohlcv['close']),float(ohlcv['volume']))
                    

                try:
                    global low,sum,dataframe,row,buy_counter,sell_counter,entry_price
                    # dataframe = self.dataframe_init()
                    ref = self.ref
                    buy_variation_dump = self.buy_variation_dump
                    buy_variation_pump = self.buy_variation_pump

                    entry_price = 0

                    entry_price = self.switch_price_reference(ref, position)

                    if takeLow:
                        entry_price -= self.pips

                    if low == 0:
                        low = position.low

                    # self.manage_alerts(position, buy_variation_dump, buy_variation_pump)

                    position.shares = self.get_balance(self.base)
                    d = self.get_transfer_balance(self.base)
                    self.balance = self.get_balance(self.quote)

                    if d > 0:
                        print(colored(f'last balance is {d}',color))
                        print(colored(f"    Entry price set to {entry_price}",color))
                        
                    orders = self.session.get_open_orders(category="spot")
                    order = None
                    orderId = None
                    if (len(orders['result']['list']) > 0):
                        order = orders['result']['list'][-1]
                        created = datetime.datetime.fromtimestamp(int(order['updatedTime'])/1000)
                        now = datetime.datetime.now()
                        elapsed = now - created
                        orderId = order['orderId']

                        if(elapsed > datetime.timedelta(seconds=float(2*self.max_wait_buy * MIN_AS_SECOND))):
                            print(colored("Elapsed order...cancel order",color))
                            self.cancel_order(order['orderId'])
                            continue
                    else:
                        position.entry_price = entry_price
                        
                    if position.shares is None or position.shares > MIN_SHARES_REQUIRED:
                        # if last_entry_price == 0:
                        if last_entry_price == 0:
                            #try to get the last entry with bybit request
                            orders = self.session.get_executions(
                                category="spot",
                                limit=50, 
                                orderStatus="Filled"
                                # symbol=base                       
                            )
                            filtered = [x for x in orders['result']['list'] if x["side"] == "Buy"]
                            l = list(filtered)
                            stats = {"avgPrice":"","symbol":self.instrument}
                            if (len(l) > 0):
                                stats = l[0]                 
                            

                            if stats['symbol'] == self.instrument:                        
                                avgPrice = stats['execPrice']
                                shares = float(stats['execQty'])
                                # status = stats['orderStatus']
                                if avgPrice not in ("",0,'0'):
                                    avgPrice = float(avgPrice)
                                    # insert last buy trade in db
                                    row.update({"details":"dernier achat récupéré via api"})
                                    row.update({"open":position.open})
                                    row.update({"high":position.high})
                                    row.update({"low":position.low})
                                    row.update({"close":position.close})
                                    row.update({"entry_price":avgPrice})
                                    row.update({"entry_date":position.date.strftime("%Y-%m-%d %H:%M:%S")})
                                    row.update({"exit_price":avgPrice+self.pips})
                                    row.update({"shares":shares})
                                    row.update({"type":"B"})
                                    row.update({"status":"Filled"})
                                    self.js_trades.insert(row)
                                else:
                                    avgPrice = position.low if MODE == 1 else position.open
                                last_entry_price = avgPrice
                                if last_exit_price == 0:
                                    last_exit_price = avgPrice + self.pips
                        # else:0x2f2B6e842c3C834031a584F6B9c3c6dB44a16383


                        if last_entry_price == 0:
                            #get the last price in db
                            Trade = Query()
                            all = self.js_trades.search(Trade.type == "B")
                            if len(all) > 0:
                                doc = all[-1]
                                last_entry_price = doc["entry_price"]


                        # last_exit_price = last_entry_price+self.pips
                        print(colored(f"    exit price setted to {last_exit_price}",color))
                        position.exit_price = last_exit_price
                        print(colored(f"    entry price setted to {last_entry_price}",color))
                        position.entry_price = last_entry_price

                        status = ''
                        if order is None:
                            print(colored(f"Exit position at {position.exit_price}",color))
                            [status,orderId] = self.exit_position( position)
                        else:
                            print(colored(f' Continue to sell at {position.exit_price}',color))

                        if status in ('Filled','New'):
                            MODE = 0
                            last_entry_price = position.entry_price
                            shares = position.shares
                            sell_counter = 0
                            cost = last_entry_price*shares                
                            earn = last_exit_price*shares
                            sum += earn - cost
                            '''
                            if sum < -10:
                                send_email(Mail_Subject.NEGATIVE_GAIN)  
                                self.done = True                      
                                exit()
                            '''
                        else:
                            created = datetime.datetime.fromtimestamp(int(order['updatedTime'])/1000)
                            now = datetime.datetime.now()
                            elapsed = now - created
                            orderId = order['orderId']
                            print(colored(f"elapsed time is {elapsed}",color))
                            if(elapsed > datetime.timedelta(seconds=float(self.max_wait_sell * MIN_AS_SECOND))):
                                print(colored("Elapsed time...need to amend order",color))
                                low = position.low
                                if MODE == 0:
                                    print(colored(' Try to sell bought price',color))
                                    last_exit_price = last_entry_price
                                    MODE = 1
                                elif MODE == 1:
                                    print(colored(' Try to sell bought price minus 1 pips',color))
                                    last_exit_price = last_entry_price-self.pips
                                    MODE = 2
                                elif MODE == 2:
                                    print(colored(' Bought price too expensive. Go out!',color))
                                    last_exit_price = low

                                if order['price'] != last_exit_price:
                                    res = self.session.amend_order(orderId = orderId,category="spot",symbol=self.instrument,price=last_exit_price)
                                    while float(res['retCode']) != 0:
                                        time.sleep(1/1000)

                        if 'status' in row and row['status'] != 'Cancelled':
                            self.js_trades.insert(row)        
                            self.trades.append(row)     
                            self.trades_persist()
                            row = {}    
        
                    else:      
                        status = ''  
                        if order is None:
                            print(colored(f"    Enter position at {position.entry_price}",color))
                            [status,orderId] = self.entry_position( position)
                        else:
                            print(colored(f'    Continue to buy at {position.entry_price}',color))

                        if status in ('Filled','New'):
                            MODE = 0
                            order = self.session.get_executions(
                                category="spot",
                                limit=1,                        
                                orderId=orderId,
                                symbol=self.instrument
                            )
                            
                            stats = order['result']['list'][0]
                            avgPrice = stats['execPrice']
                            status = 'Filled'
                            row.update({"orderId":orderId})

                            if avgPrice != "":
                                avgPrice = float(avgPrice)
                                last_entry_price = avgPrice
                                last_exit_price = avgPrice + self.pips
                                row.update({"status": status})
                                buy_counter = 0
                        else:
                            last_entry_price = float(order['price'])
                            row.update({"status":'Cancelled'})
                            
                            created = datetime.datetime.fromtimestamp(int(order['updatedTime'])/1000)
                            now = datetime.datetime.now()
                            elapsed = now - created
                            orderId = order['orderId']
                            print(colored(f"    Elapsed time is {elapsed}",color))
                            if(elapsed > datetime.timedelta(seconds=float(self.max_wait_buy * MIN_AS_SECOND))):
                                print(colored("Elapsed time...need to amend order",color))
                                low = position.low
                                open = position.open
                                last_entry_price = open
                                # if MODE == 0 else last_entry_price+self.pips
                                last_exit_price = last_entry_price+self.pips
                                
                                if order['price'] != last_entry_price and order['price'][:-1] != '-':
                                    q = self.round_down(self.balance/last_entry_price,2)
                                    # print(colored(f"new quantity is {q}",color))
                                    res = self.session.amend_order(orderId = orderId,category="spot",symbol=self.instrument,price=last_entry_price,qty=q)
                                    while float(res['retCode']) != 0:
                                        time.sleep(1/1000)

                        if row['status'] != 'Cancelled':
                            self.js_trades.insert(row)        
                            self.trades.append(row)     
                            self.trades_persist()
                            row = {}    

                    time.sleep(2)
                    
                except Exception as ex:
                    print(str(ex))
                    print(str(ex.__traceback__.tb_lineno))
                    print(str(ex.__traceback__.tb_lasti))
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

    def switch_price_reference(self, ref, p):
        o = p.open
        h = p.high
        l = p.low
        c = p.close

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
        shares = (self.balance) / entry_price
        if not self.checkVolume or position.volume >= shares:
            result = {}
            status = ''
            orderId = ''
            try:
                result = self.add_entry(position,shares)
                if result is not None:
                    [status,orderId] = self.manage_order(result)

            except Exception as ex:
                print((str(ex)))
                print(str(ex.__traceback__.tb_lineno))

            last_entry_price = entry_price
            last_exit_price = last_entry_price+self.pips
            return [status,orderId]
        
        else:
            row.update({"details":f"Pas assez de volume pour acheter"})
            buy_counter += 1
            
        return ['','']

    def add_entry(self,p,s):
                try:
                    price = position.entry_price
                    result = self.session.place_order(category="spot",
                    symbol=self.instrument,
                    side="Buy",
                    orderType="Limit",
                    qty=self.round_down(s,2),
                    price=self.round_down(price,6),
                    timeInForce="GTC",
                    # orderLinkId="spot-test-postonly",
                    isLeverage=0,
                    orderFilter="Order") 
                    row.update({"details":f"Achat a {price} sur la bougie du {p.date}"})
                    row.update({"open":p.open})
                    row.update({"high":p.high})
                    row.update({"low":p.low})
                    row.update({"close":p.close})
                    row.update({"entry_price":price})
                    row.update({"entry_date":p.date.strftime("%Y-%m-%d %H:%M:%S")})
                    row.update({"exit_price":price+self.pips})
                    row.update({"shares":s})
                    row.update({"type":"B"})
                    
                    return result

                except Exception as ex:
                    print((str(ex)))
                    print(str(ex.__traceback__.tb_lineno))
                
    def add_exit(self,p,s):
        result = {}
        try:
            price = position.exit_price
            result = self.session.place_order(category="spot",
            symbol=self.instrument,
            side="Sell",
            orderType="Limit",
            qty=self.round_down(s,6),
            price=self.round_down(price,4),
            timeInForce="GTC",
            isLeverage=0,
            orderFilter="Order") 

            row.update({"details":f"VENTE a {price} sur la bougie du {p.date}"})
            row.update({"open":p.open})
            row.update({"high":p.high})
            row.update({"low":p.low})
            row.update({"close":p.close})
            row.update({"exit_date":p.date.strftime("%Y-%m-%d %H:%M:%S")})
            row.update({"entry_price":position.entry_price})
            row.update({"exit_price":price})
            row.update({"shares":s})
            row.update({"type":"S"})
            row.update({"balance":sum})

            return result

        except Exception as e:
            print((str(e)))
            print(str(e.__traceback__.tb_lineno))

    def exit_position(self, position):
        global sell_counter,sum,row
        global low
        try:
            x = position.open if position.exit_price == 0 else self.round_down(position.exit_price,4)
            position.exit_price = x
            d = position.date
        except Exception as e:
            print((str(e)))
            print(str(e.__traceback__.tb_lineno))

        # if o == x:
        status = ''
        orderId = ''
        s = position.get("shares")
        if not self.checkVolume or s <= self.avgVolume:
            try:
                result = self.add_exit(x,s,position)
                if result is not None:
                    [status,orderId] = self.manage_order(result)

            except Exception as e:
                print((str(e)))
                print(str(e.__traceback__.tb_lineno))
            
                    # if (earn < cost): print(balance+oldsum,balance+sum)

            low = position.low
            return [status,orderId]      
        else:
            sell_counter += 1

        return ['','']      

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

