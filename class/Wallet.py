from termcolor import colored
class Wallet:

    sessionmanager = None

    def __init__(self,sess) -> None:
        self.sessionmanager = sess

    def get_balance(self,token):
        try:            
            assets = self.sessionmanager.get_coin_balance(
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
            assets = self.sessionmanager.get_coin_balance(
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
            balance = self.sessionmanager.get_wallet_balance(accountType="UNIFIED")
            self.balance = balance["totalEquity"]
            return balance
        except Exception as ex:
            print(colored('@ERROR@','light_red'))
            print("     " +  str(ex))
            print("     " +str(ex.__traceback__.tb_lineno))
            print("     " +str(ex.__traceback__.tb_lasti))
