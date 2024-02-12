import datetime
import time

from tinydb import Query
from Buy import Buy
from Order import Order

from Sell import Sell
from Trade import Trade
from Wallet import Wallet
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
    def __init__(self,b,q,msw,mbw,r,svd,bvd,svp,bvp,base,quote,session,common):
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
        
        self.sessionmanager = session
        # self.clean_trades()
        self.done = False
        self.trademanager = {}
        self.commonmanager = common
        self.walletmanager = common.walletmanager
        self.ordermanager = Order(session,common)
        self.sellmanager = Sell(self.ordermanager)
        self.buymanager = Buy(self.ordermanager)

        self.df_trades = common.persistence_init()

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

    def process(self):
        global quantity,exit_price,entry_price,color
        self.trademanager = Trade()   

        sellmanager = self.sellmanager
        buymanager = self.buymanager

        sellmanager.trade = self.trademanager
        buymanager.trade = self.trademanager
   
        self.done = False
        while True:
            if not self.done:
                color = self.trademanager.getTradeLevel()
                print(colored('Process on last candle...',color))        
        
                try:
                    order = None
                    orders = self.sessionmanager.get_executions(
                        category="spot",
                        limit=1, 
                        orderStatus="Filled",
                    )
                    last_order_executed_side = 'Buy'
                    last_order_executed = {}

                    if len(orders['result']['list']) > 0:
                        last_order_executed = orders['result']['list'][0]                
                        last_order_executed_side = last_order_executed['side']
                        last_order_executed_orderId = last_order_executed['orderId']

                    if last_order_executed_side == 'Buy':
                        if self.trademanager.position != None:
                            print(colored('on vérifie si on a pas déja record la transaction'))
                            if len(self.trademanager.trades) == 0 or self.trademanager.trades[0]['orderId'] != last_order_executed_orderId:
                                print(colored('on enregistre le dernier achat'))
                                self.trademanager.position.entry_price = last_order_executed['execPrice']
                                row = self.buymanager.valid_entry(last_order_executed_orderId)  
                                self.trademanager.trades = []
                                self.trademanager.trades.append(row)
                                self.trademanager.trades_persist()                                

                        print(colored('La dernière transaction est un achat, on vends','blue'))
                        print(colored(' on teste si on a pas déja un ordre en corus de vente','blue'))
                        orders = self.sessionmanager.get_open_orders(
                        category="spot",
                        limit=1,                        
                        symbol=self.instrument,
                        side = 'Sell'
                        )

                        if len(orders['result']['list']) > 0:
                            order = orders['result']['list'][0]
                        # if order['price'] != '0':
                            print(colored(' Oui? on test si il est expiré ','blue'))
                            [passed,elapsed] = self.ordermanager.checkElapsedOrder(order,'Sell')
                            if elapsed:
                                print(colored(' il est expire on le mets a jour ','blue'))
                                
                                entry_price = float(last_order_executed['execPrice'])
                                self.trademanager.entry_price = entry_price

                                exit_price = float(order['price'])
                                self.trademanager.exit_price = exit_price

                                sellmanager.update_sell_price()
                                sellmanager.amend_sell(order)
                            else:
                                print(colored(passed,"light_blue"))

                        else:
                            print(colored(' Non? on crée un ordre de vente ','blue'))
                            entry_price = float(last_order_executed['execPrice'])
                            exit_price = round(entry_price + self.pips,4)
                            quantity = self.commonmanager.round_down(self.walletmanager.get_balance(self.base) / exit_price,2)
                            
                            self.trademanager.entry_price = entry_price
                            self.trademanager.exit_price = exit_price
                            self.trademanager.quantity = quantity
                            
                            self.sellmanager.sell(exit_price)
                            # self.report_filled_trade()
                            
                    else:
                        if self.trademanager.position != None:
                            print(colored('on vérifie si on a pas déja record la transaction'))
                            if len(self.trademanager.trades) == 0 or self.trademanager.trades[0]['orderId'] != last_order_executed_orderId:
                                print(colored('on enregistre la dernière vente'))
                                self.trademanager.position.exit_price = float(last_order_executed['execPrice'])
                                row = self.sellmanager.valid_exit(last_order_executed_orderId)
                                self.trademanager.trades = []
                                self.trademanager.trades.append(row)
                                self.trademanager.trades_persist()                                
                        print(colored('La dernière transaction est une vente, on achète','blue'))
                        print(colored(' on teste si on a pas déja un ordre en corus d''achat','blue'))
                        orders = self.sessionmanager.get_open_orders(
                        category="spot",
                        limit=1,                        
                        symbol=self.instrument,
                        side = 'Buy'
                        )
                        if len(orders['result']['list']) > 0:
                            order = orders['result']['list'][0]
                            print(colored(' Oui? on test si ce il est expiré ','blue'))
                            [passed,elapsed] = self.ordermanager.checkElapsedOrder(order,'Buy')
                            if elapsed:
                                print(colored(' il est expire on le mets a jour ','blue'))
                                entry_price = self.buymanager.update_buy_price()
                                self.trademanager.entry_price = entry_price
                                print(colored(f'prix entree a {entry_price}'),'blue')
                                self.buymanager.amend_buy(order)
                            else:
                                print(colored(passed,'light_cyan'))
                        else:
                            print(colored(' Non? on crée un ordre pour acheter ','blue'))
                            position = self.buymanager.buy()
                            # self.report_filled_trade()

                except Exception as ex:
                    print(colored('@ERROR@','light_red'))
                    print("     " +  str(ex))
                    print("     " +str(ex.__traceback__.tb_lineno))
                    print("     " +str(ex.__traceback__.tb_lasti))

                time.sleep(50)
                continue


            else:
                time.sleep(2)
                self.done = False
