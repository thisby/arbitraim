from termcolor import colored

class Buy:

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

    def update_buy_price(self):        
        global color,last_entry_price
        print(colored("Elapsed time...need to amend order",color))
        position = self.get_last_position()
        low = position.low
        open = position.open
        last_entry_price = open
        # if MODE == 0 else last_entry_price+self.pips
        return last_entry_price
    
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
