import datetime
from src.pyalgotrade.pyalgotrade.bar import Bar,Bars
import pandas as pd


pips = 1 / 10000
instrument = "USDC"
sell_counter = 0
buy_counter = 0
max_sell_wait = 30
max_buy_wait = 30
runDate = datetime.datetime.now()
# low = 1.0002
balance = 10000
shares = 0
position = {"type":"","entry_price":"","entry_date":"","exit_price":"","exit_date":""}
df1 = pd.read_csv(f'./data/bybit/USDC/data_2D_20230701_1m.csv',delimiter=',')
df1 = df1.rename(columns={"Date Time":"date"})
first_use_case_date = 0
df1["entry_date"] = ""
df1["entry_price"] = 0
df1["exit_price"] = 0
df1["shares"] = ""
df1["type"] = "N"
df1["exit_date"] = ""
df1["details"] = ""
avgVolume = df1["Volume"].mean()


sum = 0
low = 0


for i in df1.index:
    d = df1.iloc[i,0]
    # o = float(values[1])
    o = df1.iloc[i,1]
    

    # h = float(values[2])
    h = df1.iloc[i,2]

    c = df1.iloc[i,4]

    # v = float(values[5])
    v = df1.iloc[i,5]

    p = 0
    df2 = pd.DataFrame()
    q = pd.DataFrame()

    if low == 0:
        first_use_case_date = df1.iloc[i,0]
        first_use_case_date = datetime.datetime.strptime(str(first_use_case_date), '%Y-%m-%d %H:%M:%S').date()
        low = df1.iloc[i,3]
        continue

    if position["type"] == "":
        if o == low:
            shares = (balance + sum) / o 
            if avgVolume >= shares:
                df1.loc[df1["date"] == d,["entry_price"]] = o
                df1.loc[df1["date"] == d,["entry_date"]] = d
                df1.loc[df1["date"] == d,["exit_price"]] = o+pips
                df1.loc[df1["date"] == d,["shares"]] = (balance + sum) / o
                df1.loc[df1["date"] == d,["details"]] = f"1ere entrée, ACHAT au prix de {o} sur la bougie du {d}"
                df1.loc[df1["date"] == d,["type"]] = "B"
                df1.astype({"exit_price":float,"entry_price":float})

                position["type"] = "B"
                position["entry_price"] = o
                position["entry_date"] = d
                position["exit_price"] = o+pips
                position["shares"] = (balance + sum) / o
            else:
                df1.loc[df1["date"] == d,["details"]] = f"Pas assez de volume pour acheter"
                
        else:
            df1.loc[df1["date"] == d,["type"]] = "N"
            df1.loc[df1["date"] == d,["entry_date"]] = d
            df1.loc[df1["date"] == d,["details"]] = f"On passe bougie suivante"

                
    elif position['type'] == "B":
        x = position["exit_price"]
        if o == x:
            s = position["shares"]
            if s<=avgVolume:
                df1.loc[df1["date"] == d,["type"]] = "S"
                df1.loc[df1["date"] == d,["exit_price"]] = x
                df1.loc[df1["date"] == d,["exit_date"]] = d
                df1.loc[df1["date"] == d,["details"]] = f"VENTE a {x} sur la bougie du {d}"
                df1.astype({"exit_price":float})

                position["type"] = "S"
                p = position['entry_price']
                cost = p*s
                
                position["exit_date"] = d
                position["exit_price"] = x
                earn = x*s
                oldsum = sum
                
                sum += earn - cost

                # if (earn < cost): print(balance+oldsum,balance+sum)

                position['balance'] = sum
                position["shares"] = 0
                low = df1.iloc[i,3]
                sell_counter = 0
            else:
                df1.loc[df1["date"] == d,["details"]] = f"Pas assez de volume pour vendre"
                sell_counter += 1

        else:
            sell_counter += 1
            if sell_counter > max_sell_wait:
                sell_counter = 0
                low = df1.iloc[i,3]
                position["exit_price"] = low
                df1.loc[df1["date"] == d,["exit_price"]] = low
                df1.loc[df1["date"] == d,["details"]] = f"VENTE FORCE a {low}"
            else:
                df1.loc[df1["date"] == d,["exit_price"]] = low
                df1.loc[df1["date"] == d,["type"]] = "N"
                df1.loc[df1["date"] == d,["entry_date"]] = d
                df1.loc[df1["date"] == d,["details"]] = f"On passe bougie suivante"

    elif position['type'] == "S":        
        if o == low:
            shares = (balance + sum) / o 
            if v >= shares:
                df1.astype({"entry_price":float})
                df1.loc[df1["date"] == d,["details"]] = f"ACHAT a {o} sur la bougie du {d}"
                df1.loc[df1["date"] == d,["entry_price"]] = o
                df1.loc[df1["date"] == d,["entry_date"]] = d
                df1.loc[df1["date"] == d,["exit_price"]] = o+pips
                df1.loc[df1["date"] == d,["shares"]] = (balance + sum) / o
                df1.loc[df1["date"] == d,["type"]] = "B"

                position["type"] = "B"
                position["exit_date"] = ""
                position["entry_date"] = d
                position["entry_price"] = o
                position["shares"] = (balance + sum) / o
                position["exit_price"] = o+pips
                buy_counter = 0
            else:
                df1.loc[df1["date"] == d,["details"]] = f"Pas assez de volume pour acheter"
                buy_counter += 1
        else:
            buy_counter += 1
            if buy_counter > max_buy_wait:
                buy_counter = 0
                low = df1.iloc[i,3]
                df1.loc[df1["date"] == d,["details"]] = f"REAJUSTEMENT PRIX ACHAT a {low}"
            else:
                df1.loc[df1["date"] == d,["type"]] = "N"
                df1.loc[df1["date"] == d,["entry_date"]] = d
                df1.loc[df1["date"] == d,["details"]] = f"On passe bougie suivante"
                
# print(positions)
print(balance + sum)
print(avgVolume)
df1.to_csv(f"Report[MAJ{runDate}]_FILLED_2D_{first_use_case_date}.csv",decimal=',')