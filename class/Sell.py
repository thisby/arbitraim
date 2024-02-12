from termcolor import colored

from Trade import Trade
FILLED = 'Filled'
UNFILLED = 'Unfilled'

class Sell:
    trade = Trade()

    def __init__(self,ordermgr):
        self.ordermanager = ordermgr
        self.commonmanager = ordermgr.commonmanager
        self.walletmanager = self.commonmanager.walletmanager
        print("Sell manager initiated")

    def sell(self,exit_price):
        COLOR = self.trade.getTradeLevel()
        try:
            print(colored("cas de vente","blue"))
            print(colored(f"Exit position at {exit_price}",COLOR))
            [status,order] = self.exit_position()
            self.trade.position = self.commonmanager.get_last_position()
            if order is not None and 'result' in order:
                last_order_id = order['result']['orderId']

        except Exception as ex:
            print(colored('@ERROR@','light_red'))
            print("     " +  str(ex))
            print("     " +str(ex.__traceback__.tb_lineno))
            print("     " +str(ex.__traceback__.tb_lasti))

    def manage_filled_exit(self,id):
        global position,entry_price,exit_price
        try:
            order = self.ordermanager.sessionmanager.get_executions(
                category="spot",
                limit=1,                        
                orderId=id,
                symbol=self.ordermanager.commonmanager.instrument,
                orderStatus=FILLED
            )

            if len(order['result']['list']) == 0:
                return order
                
            print(f"get order with {id}, {self.ordermanager.commonmanager.instrument}")
            stats = order['result']['list'][0]

            avgPrice = stats['execPrice']
            quantity = float(stats['execQty'])
            self.valid_exit(id)

            if avgPrice != "":
                avgPrice = float(avgPrice)
                entry_price = avgPrice
                exit_price = round(avgPrice + self.commonmanager.pips,4)
            
            return order
        
        except Exception as ex:
            print(colored('@ERROR@','light_red'))
            print("     " +  str(ex))
            print("     " +str(ex.__traceback__.tb_lineno))
            print("     " +str(ex.__traceback__.tb_lasti))

    def amend_sell(self,order):
        self.ordermanager.amend_order(self.trade.exit_price,order,'sell')

    def update_sell_price(self):
        entry_price = self.trade.entry_price
        exit_price = self.trade.exit_price
        COLOR = self.trade.getTradeLevel()
        print(colored("Elapsed time...need to amend order",COLOR))
        mode = self.trade.MODE
        if mode == 0:
            exit_price = round(entry_price,4)
            print(colored(f' Try to sell bought price : {exit_price}',COLOR))
            mode = 1
        elif mode == 1:
            exit_price = round(entry_price-self.commonmanager.pips,4)
            print(colored(f' Try to sell bought price minus 1 pips: {exit_price}',COLOR))
            mode = 2
        elif mode == 2:
            sell_position = self.ordermanager.commonmanager.get_last_position()
            exit_price = round(sell_position.low,4)
            print(colored(f' Bought price too expensive. Go out! :  {exit_price}',COLOR))
        
        self.trade.exit_price = exit_price
        self.trade.MODE = mode
        return exit_price

    def add_exit(self):
        result = {}
        try:
            price = self.trade.exit_price
            result = self.ordermanager.sessionmanager.place_order(category="spot",
            symbol=self.ordermanager.commonmanager.instrument,
            side="Sell",
            orderType="Limit",
            qty=self.ordermanager.commonmanager.round_down(self.trade.quantity,6),
            price=self.ordermanager.commonmanager.round_down(price,4),
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
        try:
            status = ''
            orderId = ''
            if not self.ordermanager.commonmanager.checkVolume or self.trade.quantity <= self.ordermanager.commonmanager.avgVolume:
                order = self.add_exit()
                if order is not None:
                    [status,orderId] = self.ordermanager.manage_order(order)
                
                if status == "Filled":
                    order = self.manage_filled_exit(orderId)

                return [status,order]      
                
        except Exception as ex:
            print(colored('@ERROR@','light_red'))
            print("     " +  str(ex))
            print("     " +str(ex.__traceback__.tb_lineno))
            print("     " +str(ex.__traceback__.tb_lasti))
            
    def valid_exit(self,id):
        position = self.trade.position
        row = {}
        sum = 0
        row.update({"details":f"VENTE a {position.exit_price} sur la bougie du {position.date}"})
        row.update({"open":position.open})
        row.update({"high":position.high})
        row.update({"low":position.low})
        row.update({"close":position.close})
        row.update({"exit_date":str(position.date)})
                    # .strftime("%Y-%m-%d %H:%M:%S")})
        row.update({"entry_price":position.entry_price})
        row.update({"exit_price":position.exit_price})
        row.update({"shares":position.shares})
        row.update({"type":"S"})
        row.update({"balance":sum})
        row.update({"status":"Filled"})
        row.update({"orderId":id})
        return row
