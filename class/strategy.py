import asyncio
import datetime
import json
import time
import pandas as pd

from tinydb import Query, TinyDB
from queue import PriorityQueue
from Mail_Subject import Mail_Subject

from Position import Position
from Reference import Reference
from mail import send_email


pips = 1/10000
takeLow = True
api_key="tOkx1lElyxcjnegbFw",
api_secret="i9qYG3cVycnZCAWdBR0WVa6FcZlYvsnzpicP",
# compte trading
api_key = "WMQ7ZAe2DIQNMjPoSE"
api_secret = "Qe7lJGokH8OPphTI2EHkR54RXkOkPMIp1C4F"
MIN_SHARES_REQUIRED = 9
MAX_RUNNING_TIME = 300
MIN_AS_SECOND = 60
MODE = 0 # 1 for cool mode (low price selling), 0 for aggressive (entry price selling)
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
        self.max_try_to_sell = msw
        self.max_try_to_buy = mbw
        self.trades = []
        self.max_wait_sell = 30
        self.max_wait_buy = 30

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
            isFilled = status == 'Filled'
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
                order = self.session.get_order_history(
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
        status = ""
        ohlcv = None
        while True:
            if not self.done:
                print('Process on last candle...')
                persistType = 'tinyDB'
                
                if persistType == 'dataframe':
                    j = ohlcv[-1].to_json()
                    s = json.loads(j) 
                    position = Position( datetime.datetime.fromtimestamp(s['0']/1000),float(s[1]),float(s[2]),float(s[3]),float(s[4]),float(s[5]))
                elif persistType == "queue":
                    # s = queue.get()
                    position = Position(float(s[0]),float(s[1]),float(s[2]),float(s[3]),float(s[4]),float(s[5]))
                elif persistType == "tinyDB":
                    all = self.ohlcv.all()
                    if status == 'Filled' or ohlcv == None:
                        ohlcv = all[-1]
                    self.ohlcv.truncate()
                    position = Position(datetime.datetime.fromtimestamp(ohlcv['start']/1000),float(ohlcv['open']),float(ohlcv['high']),float(ohlcv['low']),float(ohlcv['close']),float(ohlcv['volume']))

                try:
                    global last_entry_price,last_exit_price,low,sum,dataframe,row,trades,buy_counter,sell_counter,entry_price
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

                    position.shares = self.get_balance(self.base)
                    # d = self.get_wallet_balance()
                    d = self.get_transfer_balance(self.base)
                    self.balance = self.get_balance(self.quote)
                    
                    print(f'last balance is {d}')
                    orders = self.session.get_open_orders(category="spot")

                    if (len(orders['result']['list']) > 0):
                        order = orders['result']['list'][-1]
                        created = datetime.datetime.fromtimestamp(int(order['createdTime'])/1000)
                        now = datetime.datetime.now()
                        elapsed = now - created

                        '''
                        if (len(orders['result']['list']) < 0):
                            self.done = True
                            return
                        '''


                        if(elapsed > datetime.timedelta(seconds=float(self.max_wait_buy * MIN_AS_SECOND))):
                            print("Elapsed order...cancel order")
                            self.cancel_order(order['orderId'])
                    
                    if position.shares is None or position.shares > MIN_SHARES_REQUIRED:
                        if last_entry_price == 0:
                            #get the last price in db
                            Trade = Query()
                            all = self.js_trades.search(Trade.type == "B")
                            if len(all) > 0:
                                doc = all[-1]
                                last_entry_price = doc["entry_price"]

                        if last_entry_price == 0:
                            #try to get the last entry with bybit request
                            orders = self.session.get_order_history(
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
                                self.done = True                      
                                exit()
                        else:
                            sell_counter += 1
                            if sell_counter > self.max_try_to_sell:
                                sell_counter = 0
                                low = position.low
                                last_exit_price = low if MODE == 1 else last_entry_price
                                last_entry_price = last_exit_price-self.pips


                        self.js_trades.insert(row)        
                        self.trades.append(row) 
                        row = {}  

                    else:        
                        [status,orderId] = self.entry_position( position)
                        isFilled = status == 'Filled'
                        if isFilled:
                            order = self.session.get_order_history(
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
                                last_entry_price = low if MODE == 1 else last_entry_price-1
                                last_exit_price = last_entry_price+self.pips

                        self.trades.append(row)     
                        row = {}    

                    self.done = True
                    time.sleep(1)
                except Exception as ex:
                    print(str(ex))
                    print(str(ex.__traceback__.tb_lineno))
                    print(str(ex.__traceback__.tb_lasti))
            else:
                time.sleep(1)
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

            last_entry_price = position.low
            last_exit_price = position.low+self.pips
            return [status,orderId]
        
        else:
            row.update({"details":f"Pas assez de volume pour acheter"})
            buy_counter += 1
            
        return ['','']

    def add_entry(self,p,s):
                try:
                    result = self.session.place_order(category="spot",
                    symbol=self.instrument,
                    side="Buy",
                    orderType="Limit",
                    qty=self.round_down(s,2),
                    price=self.round_down(entry_price,6),
                    timeInForce="GTC",
                    # orderLinkId="spot-test-postonly",
                    isLeverage=0,
                    orderFilter="Order") 
                    row.update({"details":f"VENTE a {entry_price} sur la bougie du {p.date}"})
                    row.update({"open":p.open})
                    row.update({"high":p.high})
                    row.update({"low":p.low})
                    row.update({"close":p.close})
                    row.update({"entry_price":entry_price})
                    row.update({"entry_date":p.date.strftime("%Y-%m-%d %H:%M:%S")})
                    row.update({"exit_price":entry_price+self.pips})
                    row.update({"shares":s})
                    row.update({"type":"B"})
                    
                    return result

                except Exception as ex:
                    print((str(ex)))
                    print(str(ex.__traceback__.tb_lineno))
                
    def add_exit(self,x,s,p):
        result = {}
        try:
            result = self.session.place_order(category="spot",
            symbol=self.instrument,
            side="Sell",
            orderType="Limit",
            qty=self.round_down(s,6),
            price=self.round_down(x,6),
            timeInForce="GTC",
            isLeverage=0,
            orderFilter="Order") 

            row.update({"details":f"VENTE a {x} sur la bougie du {p.date}"})
            row.update({"open":p.open})
            row.update({"high":p.high})
            row.update({"low":p.low})
            row.update({"close":p.close})
            row.update({"exit_date":p.date.strftime("%Y-%m-%d %H:%M:%S")})
            row.update({"exit_price":x})
            row.update({"shares":s})
            row.update({"type":"S"})
            row.update({"balance":sum})

            return result

        except Exception as e:
            print((str(e)))
            print(str(e.__traceback__.tb_lineno))

    def exit_position(self, position):
        global sell_counter,sum,last_entry_price,last_exit_price,row
        global low
        try:
            x = position.open if last_exit_price == 0 else self.round_down(last_exit_price,6)
            last_exit_price = x
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

