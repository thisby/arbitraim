from termcolor import colored

from Trade import Trade

class Sell:

    trade = Trade()

    def __init__(self):
        print("Sell manager initiated")

    def sell(self,exit_price):
        COLOR = self.trade.getTradeLevel()
        try:
            print(colored("cas de vente","blue"))
            print(colored(f"Exit position at {exit_price}",COLOR))
            [status,order] = self.exit_position()
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

    def amend_sell(self,order):
        global exit_price
        self.amend_order(exit_price,order,'sell')

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
            exit_price = round(entry_price-self.pips,4)
            print(colored(f' Try to sell bought price minus 1 pips: {exit_price}',COLOR))
            mode = 2
        elif mode == 2:
            sell_position = self.get_last_position()
            exit_price = round(sell_position.low,4)
            print(colored(f' Bought price too expensive. Go out! :  {exit_price}',COLOR))
        return exit_price

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
