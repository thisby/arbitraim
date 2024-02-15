import datetime
import time
from termcolor import colored

MIN_AS_SECOND = 60
MAX_WAIT_SELL = 45
MAX_WAIT_BUY = 15
FILLED = 'Filled'
UNFILLED = 'Unfilled'

class Order:
    
    order = None

    def __init__(self,sess,common) -> None:
        self.sessionmanager = sess
        self.commonmanager = common
        self.walletmanager = common.walletmanager
        
    def amend_order(self,price,order,side):
        try:
            orderId = order['orderId']
            instrument = self.commonmanager.quote if side == 'buy' else self.commonmanager.base
            balance = self.commonmanager.round_down(self.walletmanager.get_balance(instrument),2)
            quantity = self.commonmanager.round_down(balance / price,2)
            amend_price = round(float(self.commonmanager.position.high)+(2*self.commonmanager.pips),4)
            if float(order['price']) != price:
                res = self.sessionmanager.amend_order(orderId = orderId,category="spot",symbol=self.commonmanager.instrument,price=price,qty=quantity)
            else:
                res = self.sessionmanager.amend_order(orderId = orderId,category="spot",symbol=self.commonmanager.instrument,price=amend_price,qty=quantity)
                while float(res['retCode']) != 0:
                    time.sleep(1/1000)
                res = self.sessionmanager.amend_order(orderId = orderId,category="spot",symbol=self.commonmanager.instrument,price=price,qty=quantity)

            while float(res['retCode']) != 0:
                time.sleep(1/1000)

        except Exception as ex:
            print(colored('@ERROR@','light_red'))
            print("     " +  str(ex))
            print(order + " vs " + price)
            print("     " +str(ex.__traceback__.tb_lineno))
            print("     " +str(ex.__traceback__.tb_lasti))

    def cancel_order(self,orderId):
        global row
        isCanceled = False
        while not isCanceled:   # on boucle jusqu'a annuler l'ordre
            orderResult = self.cancel_order(
                category="spot",
                orderId=orderId,
                symbol=self.commonmanager.instrument
            )
            isCanceled = True
            status = orderResult["retCode"]
            if status == 0:
                status = 'Cancelled'
                isCanceled = True
    
        if isCanceled:
            row.update({'status':status})        

    def manage_order(self,orderResult,isIOT = False):
        try:
            orderId = orderResult['result']['orderId']
            status = self.manage_status(orderId)
            timeout = 0
            if status == "Filled": # l'ordre n'est pas rempli
                if (not isIOT):# si on attends une annulation d'ordre
                    max_wait = MAX_WAIT_SELL if orderResult['result']['side'] == 'Sell' else MAX_WAIT_BUY
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

    def manage_status(self,orderId):
        try:
            status = ''
            order = self.sessionmanager.get_executions(
                category="spot",
                limit=1,                        
                orderId=orderId,
                symbol=self.commonmanager.instrument,
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

    def checkElapsedOrder(self,order,side):
        created = datetime.datetime.fromtimestamp(int(order['updatedTime'])/1000)
        now = datetime.datetime.now()
        elapsed = now - created
        max_wait = MAX_WAIT_BUY if side == 'Buy' else MAX_WAIT_SELL
        return [elapsed,(elapsed > datetime.timedelta(seconds=max_wait * MIN_AS_SECOND))] 