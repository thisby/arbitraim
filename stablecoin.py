
from bs4 import BeautifulSoup
import csv
import datetime
# from __future__ import print_functio
import logging
import os
import threading
import time
import pandas as pd
import pdfkit as pdfk
import sys
from src.pyalgotrade.pyalgotrade import strategy
from src.pyalgotrade.pyalgotrade.broker import Order, OrderExecutionInfo
from src.pyalgotrade.pyalgotrade.strategy.position import LongPosition, Position


from src.pyalgotrade.pyalgotrade.stratanalyzer import returns
from src.pyalgotrade.pyalgotrade.stratanalyzer import trades
from src.pyalgotrade.pyalgotrade.stratanalyzer import sharpe
from src.pyalgotrade.pyalgotrade.stratanalyzer import drawdown

global headers
headers = ["type","amount","open_rate","close_rate","O","H","L","C","open_date","close_date","Entry volume","Exit Volume","compteur entree","compteur sortie","compteur annulation"]
excel_header = 'data:text/csv;charset=utf-8,'



class PriceAction(strategy.BacktestingStrategy):
    global headers
    def __init__(self, feed, instrument,run, entry_candle_waiting = 30,entry_pips = 1):
        super(PriceAction, self).__init__(feed, 1000)
        self.waiting_exit = run
        self.broker = self.getBroker()
        self.strat = self.broker.getFillStrategy()
        self.entry_price = 0 
        self.pips = entry_pips  
        self.logs = []
        self.excel = 0
        self.epsilon = self.pips / 10000
        self.runDate = datetime.datetime.now()
        self.entry_candle_waiting = 30
        self.exit_candle_waiting = 30
        self.cancel_exit_candle_waiting = 30
        self.entry_counter_candle = 0
        self.exit_counter_candle = 0
        self.cancel_exit_counter_candle = 0
        self.__position = None
        self.__closeDS = feed[instrument].getCloseDataSeries()
        self.__openDS = feed[instrument].getOpenDataSeries()
        self.__highDS = feed[instrument].getHighDataSeries()
        self.__lowDS = feed[instrument].getLowDataSeries()
        self.__volumeDS = feed[instrument].getVolumeDataSeries()
        self.__dateDS = feed[instrument].getDateTimes()
        self.__instrument = instrument
        self.exitRequestCanceled = False
        self.show_info = False
        self.show_debug = False

        self.result = []
        # self.setDebugMode(False)
        if not self.show_info:
            with open(f'data-{self.pips}pips-{self.__instrument}-{self.runDate}.csv', 'a', encoding='UTF8') as f:
                writer = csv.writer(f,delimiter=";",dialect="excel")
                if self.excel:
                    headers.insert(0,excel_header.replace('"',''))
                # write the header
                writer.writerow(headers)
        self.retAnalyzer = returns.Returns()
        self.attachAnalyzer(self.retAnalyzer)
        self.sharpeRatioAnalyzer = sharpe.SharpeRatio()
        self.attachAnalyzer(self.sharpeRatioAnalyzer)
        self.drawDownAnalyzer = drawdown.DrawDown()
        self.attachAnalyzer(self.drawDownAnalyzer)
        self.tradesAnalyzer = trades.Trades()
        self.attachAnalyzer(self.tradesAnalyzer)
        # self.strat.setVolumeLimit(None)
    
    def infos(self,msg,date = None):
        if self.show_info:
            self.info(msg)
        if date is not None:
            self.addLog(msg,date)
    
    def debugs(self,msg):
        if self.show_debug:
            self.debug(msg)

    def onStart(self):
        logger = self.getLogger()
        logger.setLevel(logging.DEBUG)        
    

    def onEnterOk(self, position):
        execInfo = position.getEntryOrder().getExecutionInfo()   
        self.entry_date = execInfo.getDateTime()
        self.entry_price = execInfo.getPrice()
        self.exit_price = self.entry_price + self.epsilon
        # self.recordTrade(execInfo.getPrice(),self.entry_date,self.open_price,self.high_price,self.low_price,self.close_price,execInfo.getQuantity(),self.entry_volume,0,"B")
        self.infos(f"BUY at $%.5f de {execInfo.getQuantity()} au {self.entry_date}, honore le {execInfo.getDateTime()}" % (execInfo.getPrice()),self.current_date)

    def onEnterCanceled(self, position):
        self.__position = None

    def onExitOk(self, position):
        execInfo = position.getExitOrder().getExecutionInfo()
        self.exit_date = execInfo.getDateTime()
        self.exit_price = execInfo.getPrice()
        # self.recordTrade(execInfo.getPrice(),self.exit_date,self.open_price,self.high_price,self.low_price,self.close_price,execInfo.getQuantity(),self.entry_volume,self.exit_volume,"S")
        self.infos(f"SELL at $%.5f de {execInfo.getQuantity()} au {self.exit_date}, honore le {execInfo.getDateTime()}" % (execInfo.getPrice()),self.current_date)
        self.__position = None

    def onOrderUpdated(self, order):
        # self.infos(str(order.getAvgFillPrice()),self.current_date)
        return super().onOrderUpdated(order)

    def onExitCanceled(self, position):
        # If the exit was canceled, re-submit it.
        self.infos("exit",self.current_date)
        self.__position.exitMarket()

    def onFinish(self,bars):
        self.info("Final portfolio value: $%.6f" % self.getResult())
        self.csvAsPdf()

    def resetCounter(self):
        self.entry_counter_candle = 0
        self.exit_counter_candle = 0
        self.cancel_exit_counter_candle = 0

    def onBars(self, bars):

        if len(self.__dateDS) == 1:
            return
        
        # Wait for enough bars to be available to calculate a SMA.
        bar = bars[self.__instrument]

        low_price = bar.getLow()
        high_price = bar.getHigh()
        close_price = bar.getClose()
        open_price = bar.getOpen()
        volume = bar.getVolume()

        self.low_price = low_price
        self.open_price = open_price
        self.high_price =  high_price
        self.close_price = close_price
        self.current_date = bar.getDateTime()

        previousDate = self.__dateDS[-2]
        previousClose = self.__closeDS[-2]
        previousOpen = self.__openDS[-2]
        previousLow = self.__lowDS[-2]
        previousHigh = self.__highDS[-2]
        previousVol = self.__volumeDS[-2]
        previousOC2 = (previousOpen + previousClose)/2

        self.debugs(f"Bougie en cours du {self.current_date} : O:{open_price},H:{high_price},L:{low_price},C:{close_price},V:{volume}")
        # self.warning(f"Bougie d'anticipation du cours du {previousDate} : O:{previousOpen},H:{previousHigh},L:{previousLow},C:{previousClose},V:{previousVol}")
        # If a position was not opened, check if we should enter a
        # long position.

        # ACHAT
        if self.__position is None:
            # self.infos("Position nulle", self.current_date)              
            if self.entry_price == 0:
                self.debugs('Aucune entree, on sette le prix d''entree au prix le plus bas precedent')   
                self.entry_price = round(previousLow,4)
            
            self.shares = (self.broker.getCash() / self.entry_price)
            self.infos(f"LOW:{str(previousLow)} / ENTRY:{str(self.entry_price)}",self.current_date)
            # if (bar.getOpen() == self.entry_price):
                # Enter a buy market order. The order is good till canceled.
            # self.infos(self.current_date,'On achète!')
            self.entry_volume = volume
            self.entry_date = self.current_date

            if self.entry_volume >= self.shares:
                self.__position = self.enterLongLimit(self.__instrument, self.entry_price,self.shares, allOrNone=True)
                # self.__position = self.enterLongStopLimit(self.__instrument,self.entry_price,self.entry_price, self.shares, True)
                
                self.debugs(' Et on reinitialise le compteur d''attente')
                self.resetCounter()
                self.recordTrade(self.entry_price,self.current_date,self.open_price,self.high_price,self.low_price,self.close_price,self.shares,volume,-1,"BOUGHT: LONG")
            else:
                self.infos(f"pas assez de volume pour acheter {self.shares} parts",self.current_date)

            if self.entry_counter_candle >= self.entry_candle_waiting:
                self.infos('     Ajustement du prix au plus bas precedent',self.current_date)   
                self.entry_price = previousLow
                self.resetCounter()
                # self.recordTrade(self.entry_price,self.current_date,self.open_price,self.high_price,self.low_price,self.close_price,self.shares,volume,-1,"BOUGHT: ADJUST")
            else:
                self.entry_counter_candle += 1
                # self.infos("on passe a la bougie suivante",self.current_date)            
                # self.recordTrade(self.entry_price,self.current_date,self.open_price,self.high_price,self.low_price,self.close_price,self.shares,volume,-1,"BOUGHT: NEXT")
        # VENTE
        elif not self.__position.exitActive():     
            # self.infos("Position non vendu",self.current_date)              
            self.exit_volume = volume
            self.exit_date = self.current_date
            if self.exit_volume >= self.shares:
                if self.open_price == self.exit_price:
                    self.exitTrade(cause='augmentation du prix ouverture',exit_price=open_price)
                    # self.__position.exitMarket()
                # self.recordTrade(self.entry_price,self.current_date,self.open_price,self.high_price,self.low_price,self.close_price,self.shares,volume,-1,"SOLD: SHORT")
            else:
                self.infos(f"pas assez de volume pour vendre {self.shares} parts",self.current_date)
    
            if self.exit_counter_candle >= self.exit_candle_waiting:
                self.debugs(f'On vends! : prix d''achat trop haut!')
                # self.infos(self.current_date,"vente")
                self.resetCounter()
                # self.infos('Vente force au prix le plus bas',self.current_date)
                self.__position.exitLimit(low_price)        
                self.recordTrade(self.entry_price,self.current_date,open_price,high_price,low_price,close_price,self.shares,volume,-1,"SOLD:FORCED")
            else:
                self.exit_counter_candle += 1
                # self.infos("on passe a la bougie suivante",self.current_date)            
                self.recordTrade(self.entry_price,self.current_date,open_price,high_price,low_price,close_price,self.shares,volume,-1,"SOLD:NEXT")
        
        else:
            # self.infos("Position en cours de vente",self.current_date)             
            if self.cancel_exit_counter_candle >= self.cancel_exit_candle_waiting:
                self.infos("annulation vente",self.current_date)
                self.resetCounter()
                self.__position.cancelExit()
                # self.recordTrade(0,self.current_date,exit_price,high_price,low_price,close_price,self.shares,volume,-1,"Selling:CANCEL")
            else:
                self.cancel_exit_counter_candle += 1
                # self.recordTrade(self.entry_price,self.current_date,exit_price,high_price,low_price,close_price,self.shares,volume,-1,"Selling:IDLE")

    def exitTrade(self,cause,exit_price):
        # self.infos(f'On vends au prix de {exit_price}! : {cause}',self.current_date)
        self.exit_counter_candle = 0        
        # self.__position = self.enterShortLimit(self.__instrument,exit_price, self.shares, True)
        # self.__position.exitLimit(exit_price)
        # self.infos("prix sortie" + str(exit_price),self.current_date)
        self.__position.exitLimit(exit_price)
        # self.info(LongPosition(self.__position).getExitOrder.getId())

    def recordTrade(self,exit_price,exit_date,open_price,high_price,low_price,close_price,shares,entry_volume,exit_volume,cssClass):        
        if cssClass.startswith("BOUGHT") or cssClass.startswith("SELLING"): 
            exit_date = ""
            entry_date = self.current_date
        elif cssClass.startswith("SOLD"):
            entry_date = self.entry_date
        trade_candle = [cssClass,shares,self.entry_price,exit_price,open_price,high_price,low_price,close_price,entry_date,exit_date,entry_volume,exit_volume,self.entry_counter_candle,self.exit_counter_candle,self.cancel_exit_counter_candle]
        with open(f'data-{self.pips}pips-{self.__instrument}-{self.runDate}.csv', 'a', encoding='UTF8') as f:
            writer = csv.writer(f,delimiter=";")
            # write the data
            writer.writerow(trade_candle)

    def addLog(self,msg,date):
        self.logs.append([date.strftime('%Y-%m-%d %H:%M:%S'),msg])
    
    def recordLog(self,date,level,msg):
        log = [date,level,msg]
        with open(f'data-{self.pips}pips-{self.__instrument}-{self.runDate}.csv', 'a', encoding='UTF8') as f:
            writer = csv.writer(f,delimiter=";")
            # write the data
            writer.writerow(log)


    def manage_result(self):
        self.result.append("Final portfolio value: $%.6f" % self.getResult())
        
        result = ""

        TA = self.tradesAnalyzer
        RA = self.retAnalyzer
        SA = self.sharpeRatioAnalyzer
        DA = self.drawDownAnalyzer

        self.result.append("Final portfolio value: $%.6f" % self.getResult())
        self.result.append("Cumulative returns: %.6f %%" % (RA.getCumulativeReturns()[-1] * 100))
        self.result.append("Sharpe ratio: %.6f" % (SA.getSharpeRatio(0.05)))
        self.result.append("Max. drawdown: %.6f %%" % (DA.getMaxDrawDown() * 100))
        self.result.append("Longest drawdown duration: %s" % (DA.getLongestDrawDownDuration()))
        self.result.append("Total trades: %d" % (TA.getCount()))
        if TA.getCount() > 0:
            profits = TA.getAll()
            self.result.append("Avg. profit: $%.6f" % (profits.mean()))
            self.result.append("Profits std. dev.: $%6f" % (profits.std()))
            self.result.append("Max. profit: $%6f" % (profits.max()))
            self.result.append("Min. profit: $%6f" % (profits.min()))
            results = TA.getAllReturns()
            self.result.append("Avg. return: %6f %%" % (results.mean() * 100))
            self.result.append("Returns std. dev.: %6f %%" % (results.std() * 100))
            self.result.append("Max. return: %6f %%" % (results.max() * 100))
            self.result.append("Min. return: %6f %%" % (results.min() * 100))

        self.result.append("Profitable trades: %d" % (TA.getProfitableCount()))
        if TA.getProfitableCount() > 0:
            profits = TA.getProfits()
            self.result.append("Avg. profit: $%6f" % (profits.mean()))
            self.result.append("Profits std. dev.: $%6f" % (profits.std()))
            self.result.append("Max. profit: $%6f" % (profits.max()))
            self.result.append("Min. profit: $%6f" % (profits.min()))
            results = TA.getPositiveReturns()
            self.result.append("Avg. return: %6f %%" % (results.mean() * 100))
            self.result.append("Returns std. dev.: %6f %%" % (results.std() * 100))
            self.result.append("Max. return: %6f %%" % (results.max() * 100))
            self.result.append("Min. return: %6f %%" % (results.min() * 100))

        self.result.append("Unprofitable trades: %d" % (TA.getUnprofitableCount()))
        if TA.getUnprofitableCount() > 0:
            losses = TA.getLosses()
            self.result.append("Avg. loss: $%6f" % (losses.mean()))
            self.result.append("Losses std. dev.: $%6f" % (losses.std()))
            self.result.append("Max. loss: $%6f" % (losses.min()))
            self.result.append("Min. loss: $%6f" % (losses.max()))
            results = TA.getNegativeReturns()
            self.result.append("Avg. return: %6f %%" % (results.mean() * 100))
            self.result.append("Returns std. dev.: %6f %%" % (results.std() * 100))
            self.result.append("Max. return: %6f %%" % (results.max() * 100))
            self.result.append("Min. return: %6f %%" % (results.min() * 100))
    
            for f in self.result:
                    result += f
                    result += "<br>"
        return result    

    def csvAsPdf(self):
        df1 = pd.read_csv(f'data-{self.pips}pips-{self.__instrument}-{self.runDate}.csv',delimiter=";")
        os.remove(f'data-{self.pips}pips-{self.__instrument}-{self.runDate}.csv')
        # df1['Details'] = ""
        html_string = df1.to_html()

        soup = BeautifulSoup("<html><head></head><body>" + html_string +"</body></html>",'lxml')
        new_style = soup.new_tag('<style>.red{background-color:#FF0000;font-weight:400}\r\n.green{background-color:#00FF00;}\r\n.blue{background-color:#0000FF;}</style>')
        soup.head.insert(0,new_style)

        i = 0

        for tr in soup('tr'):
            if i == 0:
                i += 1
                continue
            logs = ""        
            td = tr("td")
            if len(td) > 4:  
                css = td[0].get_text()                
                this = td[8] if css.startswith("BOUGHT") or css.startswith("SELLING") else td[9]
                content = this.get_text()
                filtered = filter(lambda x: x[0] == content, self.logs)
                logs += content
                logs += "\r\n"
                for f in list(filtered):
                    logs += f[1]
                    logs += "<br />"

            new_td = BeautifulSoup(f'<td>{logs}</td>',features="html.parser")
            tr.append(new_td)
            if "SELL" in logs:
                tr['class'] = 'red'
            if "BUY" in logs:
                tr['class'] = 'green'

        '''
        for td in soup('td'):
            content = td.get_text()
            tr = td.parent
            if 'SHORT' in content or 'FORCED' in content:
                tr['class'] = 'red'

            elif 'LONG' in content:
                tr['class'] = 'green'

            elif 'SELLING' in content:
                tr['class'] = 'blue'
        '''


        '''
        i = 0

        for tr in soup('tr'):
            if i == 0:
                i += 1
                continue
            logs = ""        
            td = tr("td")
            if len(td) > 4:  
                css = td[0].get_text()
                this = td[8] if css.startswith("BOUGHT") or css.startswith("SELLING") else td[9]
                content = this.get_text()
                filtered = filter(lambda x: x[0] == content, self.logs)
                logs += content
                logs += "\r\n"
                for f in list(filtered):
                    logs += f[1]
                    logs += "<br />"

            new_td = BeautifulSoup(f'<td>{logs}</td>',features="html.parser")
            tr.append(new_td)       
        '''

        with open(f"Report-{datetime.datetime.now().date()}.csv", "w") as f:
            wr = csv.writer(f)
            wr.writerow(list([excel_header]) + headers)
            wr.writerows([[td.text for td in row("td")] for row in soup("tr")])

        tr = soup('tr')[0]

        result = self.manage_result()
        
        new_td = BeautifulSoup(f'<td>{result}</td>',features="html.parser")
        tr.append(new_td)

        options = {    
            'orientation':'Landscape',
            'page-size': 'A3',
            'margin-top': '0mm',
            'margin-right': '0mm',
            'margin-bottom': '0mm',
            'margin-left': '0mm',
        }
        
        pdfk.configuration(wkhtmltopdf='/usr/bin/wkhtmltopdf')
        pdfk.from_string(str(soup), f"Report-{datetime.datetime.now().date()}.pdf",options=options)
        print("PDF file saved.")


