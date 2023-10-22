from __future__ import print_function
import csv
import datetime
import os
import sys


sys.path.append(os.getcwd() + "env/lib/python3.10/site-packages/pyalgotrade")

from pyalgotrade import strategy

headers = ["pair","amount","open_rate","close_rate","open_date","close_date","volume","profit"]
excel_header = 'data:text/csv;charset=utf-8,'



class PriceAction(strategy.BacktestingStrategy):
    def __init__(self, feed, instrument, entry_candle_waiting = 30,entry_pips = 1):
        super(PriceAction, self).__init__(feed, 1000)
        self.entry_price = 0  
        self.pips = entry_pips  
        self.excel = 1   
        self.epsilon = self.pips / 10000
        self.firstPersist = True
        self.runDate = datetime.datetime.now()
        self.entry_candle_waiting = 30
        self.exit_candle_waiting = 30
        self.entry_counter_candle = 0
        self.exit_counter_candle = 0
        self.__position = None
        self.__closeDS = feed[instrument].getCloseDataSeries()
        self.__openDS = feed[instrument].getOpenDataSeries()
        self.__highDS = feed[instrument].getHighDataSeries()
        self.__lowDS = feed[instrument].getLowDataSeries()
        self.__volumeDS = feed[instrument].getVolumeDataSeries()
        self.__dateDS = feed[instrument].getDateTimes()
        self.__stopMultiplier = 0.01
        self.__instrument = instrument

        with open(f'data-{self.pips}pips-{self.__instrument}-{self.runDate}.csv', 'a', encoding='UTF8') as f:
            writer = csv.writer(f,delimiter=";",dialect="excel")
            if self.excel:
                headers.insert(0,excel_header.replace('"',''))
            # write the header
            writer.writerow(headers)
            


        # self.offset = buy_offset
        # self.buy_percent = buy_percent

    def onEnterOk(self, position):
        execInfo = position.getEntryOrder().getExecutionInfo()
        self.info("BUY at $%.5f" % (execInfo.getPrice()))

    def onEnterCanceled(self, position):
        self.__position = None

    def onExitOk(self, position):
        execInfo = position.getExitOrder().getExecutionInfo()
        self.persist(execInfo.getPrice(),execInfo.getDateTime(),execInfo.getQuantity(),self.bar_volume)
        self.info("SELL at $%.5f" % (execInfo.getPrice()))
        self.__position = None

    def onExitCanceled(self, position):
        # If the exit was canceled, re-submit it.
        self.__position.exitMarket()

    def onFinish(self,bars):
        self.info('on finish')
        '''
        with open(f'data-{self.pips}pips-{self.__instrument}-{self.runDate}.csv', 'r', encoding='UTF8') as f:
            reader = csv.reader(f)
            for row in reader:
                print(row)
        '''
    def onBars(self, bars):
        if len(self.__dateDS) == 1:
            return
        # Wait for enough bars to be available to calculate a SMA.
        bar = bars[self.__instrument]
        previousDate = self.__dateDS[-2]
        self.info(f'Trade pour le {bar.getDateTime()}')
        self.info(f'anticipation via {previousDate}')
        previousClose = self.__closeDS[-2]
        previousOpen = self.__openDS[-2]
        previousLow = self.__lowDS[-2]
        previousHigh = self.__highDS[-2]
        previousVol = self.__volumeDS[-2]

        candle = ["",previousDate,previousOpen,previousHigh,previousLow,previousClose,previousLow]


        previousOC2 = (previousOpen + previousClose)/2
        # self.info(bar.getClose())
       # self.info(self.__sma[-1])

        bar = bars[self.__instrument]
        # If a position was not opened, check if we should enter a
        # long position.

        # ACHAT
        if self.__position is None:
            self.info('Pas d''entrée pour le moment')
            #is waiting enough?        
            self.info(' Doit-on ajuster le prix?')   
            if self.entry_counter_candle >= self.entry_candle_waiting:
            # or self.entry_counter_candle == 0:          
                self.info('     oui, on récupère le prix le plus bas précédent')   
                self.entry_price = previousLow
                self.entry_counter_candle = 0
            else:
                self.info('     non, on ne fait rien on garde la moyenne du cours de fermeture et du cours d''ouverture précédent')   
            self.info(' On incrémente le compteur d''attente pour les achats')   
            self.entry_counter_candle += 1

               
            if self.entry_price == 0:
                #this is our first entry
                self.info('Aucune entrée, on sette le prix d''entrée a la moyenne du cours de fermeture et du cours d''ouverture précédent')   
                self.entry_price = round(previousOC2,4)
            self.info(f'Prix achat {self.entry_price},balance:{self.getBroker().getCash()}')
            self.info('On calcule le nombre de tokens que l''on peut acheter')               
            shares = (self.getBroker().getCash() / self.entry_price)
            self.info('Si le prix d''ouverture ou le prix le plus de la bougie en cours est égal au prix de référence')   
            if (bar.getOpen() == self.entry_price 
                or
                bar.getLow() == self.entry_price
                # or
                # bar.getHigh() == self.entry_price
                # or
                # bar.getClose() == self.entry_price 
                ):
                # Enter a buy market order. The order is good till canceled.
                self.info('On achète!')
                self.entry_date = bar.getDateTime()   
                self.__position = self.enterLongLimit(self.__instrument,self.entry_price, shares, True)
                self.info(' Et on réinitialise le compteur d''attente')   
                self.entry_counter_candle = 0
        # VENTE
        elif not self.__position.exitActive():
            open_price = bar.getOpen()
            self.bar_volume = bar.getVolume()
            # self.info('On vends si et seulement si le prix d''ouverture ou le prix le plus bas a augmenté')   
            if (
                open_price > self.entry_price
                ):   
                self.exitTrade(cause='augmentation du prix ouverture',exit_price=open_price)
            # elif (bar.getLow() == (self.entry_price + self.epsilon)):
                # self.exitTrade(cause='augmentation du prix ouverture',exit_price=open_price)
            elif self.exit_counter_candle >= self.exit_candle_waiting:
                self.info(f'On vends! : prix d''achat trop haut!')   
                self.exit_counter_candle = 0
                # self.__position.exitMarket()
                # if self.exit_forced_counter_candle  30
                # self.exitTrade('Vente forcé au prix acheté',exit_price=self.entry_price)
                self.exitTrade('Vente forcé au prix acheté',exit_price=bar.getLow())        

            else:
                self.exit_counter_candle = self.exit_counter_candle + 1

    def exitTrade(self,cause,exit_price):
        self.info(f'On vends! : {cause}')   
        self.exit_counter_candle = 0        
        self.__position.exitLimit(exit_price)

    def persist(self,exit_price,exit_date,shares,bar_volume):
        trade_candle = [self.__instrument, shares,self.entry_price,exit_price,self.entry_date,exit_date,bar_volume,shares*(exit_price-self.entry_price)]
        with open(f'data-{self.pips}pips-{self.__instrument}-{self.runDate}.csv', 'a', encoding='UTF8') as f:
            writer = csv.writer(f,delimiter=";")
            # write the data
            writer.writerow(trade_candle)



