import pandas as pd
import ccxt
import datetime

exchange = ccxt.bybit()
base = "PYUSD"
def gather_data():
    day = '2023-09-20 00:00:00'
    start = datetime.datetime.strptime(str(day), '%Y-%m-%d %H:%M:%S')
    print(start)
    ts_start = round(start.timestamp()*1000)
    ts_end = round((start + datetime.timedelta(minutes=1000)).timestamp() * 1000)
    # print(datetime.timedelta(minutes=1000))
    lim = 2 * 24 * 60
    data =  exchange.fetch_ohlcv(f"{base}/USDT",since=ts_start,limit=10000)
    df = pd.DataFrame(data)
    data =  exchange.fetch_ohlcv(f"{base}/USDT",since=ts_end,limit=10000)
    df1 = pd.DataFrame(data)
    df = pd.concat([df,df1]).reset_index()
    df.columns = ["","Date Time", "Open", "High", "Low", "Close", "Volume"]
    def parse_dates(ts):
        return datetime.datetime.fromtimestamp(ts/1000.0)
    df["Date Time"] = df["Date Time"].apply(parse_dates)
    df.to_csv(f"./data/bybit/{base}/data_1D_20230701_1m.csv")

def main():
    gather_data()

if __name__ == "__main__":
    main()
