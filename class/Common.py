import datetime
import json
from numpy import size
import pandas as pd
from termcolor import colored
from tinydb import TinyDB
from Mail_Subject import Mail_Subject
from Position import Position

from Reference import Reference


class Common:
    
    pips = 1/10000
    checkVolume = False
    base = "USDC"
    quote = "USDT"
    instrument = base + quote
    first_use_case_date = datetime.datetime.now()
    reference = Reference.OPEN
    position = None

    def __init__(self,walletmanager) -> None:
        self.walletmanager = walletmanager
        pass

    def read_last_candle(self):
        df = pd.read_json('ohlcv.json')
        if size(df) == 0:
            return None
        j = df.iloc[-1].to_json()
        # j = ohlcv.to_json()
        s = json.loads(j)['_default']
        return s

    def parse_position(self,s):
        position = Position( datetime.datetime.fromtimestamp(s['start']/1000),float(s['open']),float(s['high']),float(s['low']),float(s['close']),float(s['volume']))
        return position
    
    def get_last_position(self):
        position = {}
        try:
            s = self.read_last_candle()
            
            if s is not None:
                position = self.parse_position(s)
                self.position = position
                return position
            
        except Exception as ex:
            print(colored('@ERROR@','light_red'))
            exception = str(ex)
            print("     " +  exception)
            print("     " +str(ex.__traceback__.tb_lineno))
            print("     " +str(ex.__traceback__.tb_lasti))
            if 'Trailing' in exception:
                return None
            else:
                exit()

    def round_down(self,f,n):
        s = str(f)
        if '.' in s:
            c = s.split('.')
            l = len(c[1])
            if l >= n+1:
                d=c[1][:n+1]
                e = d[:-1] + "0"
                return float(c[0] + "." + e)
            else:
                return f
            
    def fill_position_from_array(self,position,arr):
        setattr(position,'date',arr[0])
        setattr(position,'entry_date',arr[6])
        setattr(position,'entry_price',arr[7])
        setattr(position,'exit_price',arr[8])
        setattr(position,'shares',arr[9])
        setattr(position,'type',arr[10])
        setattr(position,'exit_date',arr[11])
        setattr(position,'details',arr[12])
        return position
    
    def fill_position_from_series(self,position,serie):
        pos = self.fill_position_from_array(position,serie.array)
        return pos
    


    def show(self,sum):
        print((self.balance + sum))
        print((self.avgVolume))
        print((str((sum/self.balance) * 100),'%'))

    def persistence_init(self):
        self.js_trades = TinyDB('trades.json')
        self.ohlcv = TinyDB('ohlcv.json')
        self.first_use_case_date = self.first_use_case_date.strftime('%Y-%m-%d %H:%M:%S')
        return pd.DataFrame(columns=["date","Open","High","Low","Close","Volume","entry_date","entry_price","exit_price","shares","type","exit_date","details","balance"])

    def manage_alerts(self, position, buy_variation_dump, buy_variation_pump):
        if last_entry_price > 0 and position.open < (last_entry_price * (1- (buy_variation_dump/100))):          
            send_email(Mail_Subject.BUY_VAR_DUMP)
            exit()

        '''
        if last_exit_price > 0 and o < (last_exit_price * (1- (sell_variation_dump/100))):          
            send_email(Mail_Subject.SELL_VAR_DUMP)
            exit()            
        '''

        if last_entry_price > 0 and position.open > (last_entry_price * (1 + (buy_variation_pump/100))):          
            send_email(Mail_Subject.BUY_VAR_PUMP)
            exit()            

        '''
        if last_exit_price > 0 and o > (last_exit_price * (1 + (sell_variation_pump/100))):          
            send_email(Mail_Subject.SELL_VAR_PUMP)
            exit()            
        '''

    def switch_price_reference(self, ref):
        position = self.get_last_position()
        o = position.open
        h = position.high
        l = position.low
        c = position.close

        if ref == Reference.OPEN:
            e = o

        if ref == Reference.HIGH:
            e = h

        if ref == Reference.HLC2:
            e = (h + l + c) /2

        if ref == Reference.HLC3:
            e = (h + l + c) /3
            
        if ref == Reference.LOW:
            e = l

        if ref == Reference.HL:
            e = (h+l)/2

        if ref == Reference.OC2:
            e = (o+c)/2
        return e
    
  

