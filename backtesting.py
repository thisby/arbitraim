# python3 strategy.py

import datetime
from multiprocessing import Process, Value
import os
import pytz
import sys


from stablecoin import PriceAction


root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(os.getcwd() + "env/lib/python3.10/site-packages/pyalgotrade")
sys.path.append(root + '/python')

from pyalgotrade import strategy
from pyalgotrade.bar import Frequency
from pyalgotrade.barfeed import csvfeed
from pyalgotrade.stratanalyzer import returns
from pyalgotrade.stratanalyzer import trades
from pyalgotrade.stratanalyzer import sharpe
from pyalgotrade.stratanalyzer import drawdown
from pyalgotrade import logger

from pyalgotrade import plotter


# shared_bool = Event()

base = "USDC"
quote = "USDT"
pair = f"{base}/{quote}"
pips = 1

import logging
import sys

file_handler = logging.FileHandler(filename=f'report-{base}-{datetime.datetime.now().date()}.log', 
   mode='w')
stdout_handler = logging.StreamHandler(stream=sys.stdout)
handlers = [file_handler, 
# stdout_handler
]

logging.basicConfig(
    level=logging.DEBUG, 
    format='[%(asctime)s] %(levelname)s - %(message)s',
    # format='%(message)s',
    handlers=handlers
)


global started

def worker(run,myStrategy):
    global started
    
    while run.value == 1:
        if not started:
            print("mystrategy running....")
            myStrategy.run()
            started = True
    else:
        print("mystrategy stop.")
        myStrategy.stop()
        started = False

def main():
    global started
    started = False
    #timezone('Europe/Monaco')
    # firstDate = datetime.datetime(2023,7,1,0,0,0,0)
    # endDate = datetime.datetime(2023,7,31,0,0,0,0)
    path = f"./data/bybit/{base}/data_2D_20230701_1m.csv"
    # path = f"./data/bybit/{base}/data_1M_20230701_1m.csv"
    feed = csvfeed.GenericBarFeed(frequency=Frequency.MINUTE)
    # feed.setBarFilter(csvfeed.DateRangeFilter(firstDate,endDate))
    feed.addBarsFromCSV(base, path)
    # run = Value("i",1)
    # Evaluate the strategy with the feed's bars.
    myStrategy = PriceAction(feed, base,run=0,entry_candle_waiting=30,entry_pips=pips)

    plt = plotter.StrategyPlotter(myStrategy)
    # Include the SMA in the instrument's subplot to get it displayed along with the closing prices.
    # plt.getInstrumentSubplot(base).addDataSeries("SMA", myStrategy.getSMA())
    # Plot the simple returns on each bar.
    # plt.getOrCreateSubplot("returns").addDataSeries("Simple returns", retAnalyzer.getReturns())

    # Run the strategy.
    # p = Process(target=myStrategy.run())
    # p.start()
    myStrategy.run()

    # Plot the strategy.
    # plt.plot()
    
if __name__ == "__main__":
    main()
