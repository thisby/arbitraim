import pandas as pd
# Import writer class from csv module
from csv import writer


class Trade:
    exit_price = 0
    entry_price = 0
    quantity = 0
    position = None
    summaries = []
    MODE = 0
    color = "white"
    js_trades = []
    trades = []

    def __init__(self) -> None:
        print("Trade manager initialized")

    def getTradeLevel(self):
        if self.MODE == 0:
            return "light_green"
        elif self.MODE == 1:
            return "light_yellow"
        else:
            return "red"
        
    def report_filled_trade(self):
        trade = self.position
        self.js_trades.insert(trade)        
        self.trades.append(trade)     
        self.trades_persist()

    def record_last_trade(self,row):
        # List that we want to add as a new row
        List = [6, 'William', 5532, 1, 'UAE']

        # Open our existing CSV file in append mode
        # Create a file object for this file
        with open('event.csv', 'a') as f_object:

            # Pass this file object to csv.writer()
            # and get a writer object
            writer_object = writer(f_object)

            # Pass the list as an argument into
            # the writerow()
            writer_object.writerow(List)

            # Close the file object
            f_object.close()



    def trades_persist(self):
        self.df_trades = pd.DataFrame(self.trades)
        self.df_trades.to_csv(f"Report.csv",decimal=',', mode='a', index=False, header=False)