import datetime


class Position:
    def __init__(self,d,o,h,l,c,v):
        self.date = d
        self.low = l
        self.high = h
        self.close = c
        self.open = o
        self.volume = v
        self.entry_price = 0        
        self.entry_date = datetime.datetime.min
        self.exit_price = 0
        self.exit_date = datetime.datetime.min
        self.details = "RAS"
        self.unfilled = 0
        self.filled = 0
        self.shares = 0
        self.type = "S"
        self.isExit = True if self.type == "S" else False
        self.isEntry = not self.isExit

    def toArray(self):
        p = [self.date,
                          self.open,
                          self.high,
                          self.low,
                          self.close,
                          self.volume,
                          self.entry_date,
                          self.entry_price,
                          self.exit_price,
                          self.shares,
                          self.type,
                          self.exit_date,
                          self.details,
                          self.filled,
                          self.unfilled,
                          self.unfilled + self.filled]
        
        # s = pd.Series(p)
        return p

    def get(self,prop):
        return getattr(self,prop)

    def set(self,prop,value):
        setattr(self,prop,value)