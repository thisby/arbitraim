from termcolor import colored

class Buy:

    ordermanager = None
    def __init__(self,ordermgr) -> None:
        self.ordermanager = ordermgr
        self.commonmanager = ordermgr.commonmanager
        self.sessionmanager = ordermgr.sessionmanager
        self.walletmanager = self.commonmanager.walletmanager

    def buy(self):
        print(colored("cas d'achat","blue"))
        print(colored("Aucun ordre en cours d'achat, création..","blue"))
        print(colored("On rentre au prix de référence","blue"))
        position = self.commonmanager.get_last_position()    
        entry_price = self.commonmanager.switch_price_reference(self.commonmanager.reference)
        quantity = self.commonmanager.round_down(self.walletmanager.get_balance(self.commonmanager.quote) / entry_price,2)
        self.trade.quantity = quantity
        self.trade.entry_price = entry_price
        position.entry_price = entry_price 
        position.exit_price = position.entry_price + self.commonmanager.pips
        self.trade.exit_price = position.exit_price

        print(colored(f"    Enter position at {position.entry_price}",self.trade.getTradeLevel()))
        [status,order] = self.entry_position()
        self.trade.position = position
        if order is not None and 'result' in order:
            last_order_id = order['result']['orderId']

        return position
    
    def amend_buy(self,order):
        self.ordermanager.amend_order(self.trade.entry_price,order,'buy')

    def update_buy_price(self):        
        print(colored("Elapsed time...need to amend order",self.trade.getTradeLevel()))
        position = self.commonmanager.get_last_position()
        low = position.low
        open = position.open
        last_entry_price = open
        # if MODE == 0 else last_entry_price+self.pips
        return last_entry_price
    
    def entry_position(self):
        position = self.commonmanager.get_last_position()
        if not self.commonmanager.checkVolume or position.volume >= self.trade.quantity:
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

            exit_price = self.trade.entry_price+self.commonmanager.pips
            return [status,orderId]
        
        else:
            buy_counter += 1
            
        return ['','']

    def add_entry(self):
        try:
            position = self.commonmanager.get_last_position()
            price = self.trade.entry_price
            result = self.sessionmanager.place_order(category="spot",
            symbol=self.commonmanager.instrument,
            side="Buy",
            orderType="Limit",
            qty=self.commonmanager.round_down(self.trade.quantity,2),
            price=self.commonmanager.round_down(price,6),
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
        position = self.trade.position
        row = {}
        row.update({"details":f"Achat a {position.entry_price} sur la bougie du {position.date}"})
        row.update({"open":position.open})
        row.update({"high":position.high})
        row.update({"low":position.low})
        row.update({"close":position.close})
        row.update({"entry_price":position.entry_price})
        row.update({"entry_date":position.date.strftime("%Y-%m-%d %H:%M:%S")})
        row.update({"exit_price":float(position.entry_price)+self.commonmanager.pips})
        row.update({"shares":position.shares})
        row.update({"type":"B"})
        row.update({"status":"Filled"})
        row.update({"orderId":id})
        return row
