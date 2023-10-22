import datetime
import itertools
import pandas as pd
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from enum import Enum

smtp_server = 'smtp.free.fr'
smtp_port = 587
smtp_username = 'ybmail@free.fr'
smtp_password = f"ethylene"

texts = {}

body = """
Bonjour,
Le dernier prix d'ouverture a subi une variation de moins de 10% par rapport au dernier prix connu .Ceci mérite peut-être votre attention
Le processus a été complètement stoppé le temps de l'analyse.
"""

texts['BUY_VAR_DUMP'] = {
    "subject":"DUMP ou KRACK en cours après achat",
    "body":body
}

body = """
        Bonjour,
            Le dernier prix d'ouverture est inférieur de 10% au prix du dernier vente.Ceci mérite peut-être votre attention
            Le processus a été complètement stoppé le temps de l'analyse.
        """

texts['SELL_VAR_DUMP'] = {
    "subject":"DUMP ou KRACK en cours après vente",
    "body":body
}


body = """
        Bonjour,
            Le dernier prix d'ouverture a subi une variation de plus de 10% par rapport au dernier prix connu.Ceci mérite peut-être votre attention
            Le processus a été complètement stoppé le temps de l'analyse.
        """

texts['BUY_VAR_PUMP'] = {
    "subject":"PUMP en cours après achat",
    "body":body
}

body = """
        Bonjour,
            Le dernier prix d'ouverture est supérieur de 10% au prix de la derniere vente.Ceci mérite peut-être votre attention
            Le processus a été complètement stoppé le temps de l'analyse.
        """

texts['SELL_VAR_PUMP'] = {
    "subject":"PUMP en cours après vente",
    "body":body
}

recipients = ['bentaleb.youness@gmail.com','f.viricel@orange.fr']

msg = MIMEMultipart()
msg['From'] = smtp_username
msg['To'] = ",".join(recipients)

def send_email(mail_subject):
    try:
        if mail_subject.name not in texts:
            return

        d = texts[mail_subject.name]

        server = smtplib.SMTP(smtp_server, smtp_port)
        msg['Subject'] = d['subject']
        msg.attach(MIMEText(d['body'], 'html'))
        server.ehlo()
        # server.starttls()  # Utilisez TLS (Transport Layer Security) pour la sécurité
        server.login(smtp_username, smtp_password)
        text = msg.as_string()
        server.sendmail(smtp_username, msg['To'], text)
        server.quit()
        print('E-mail envoyé avec succès.')
    except Exception as e:
        print('Erreur lors de l\'envoi de l\'e-mail :', str(e))

class Mail_Subject(Enum):
    BUY_VAR_DUMP = 1
    SELL_VAR_DUMP = 2
    BUY_VAR_PUMP = 3
    SELL_VAR_PUMP = 4

class Message:

    def __init__(self) -> None:
        pass


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

    
class Reference:
    OPEN = 1
    HIGH = 2
    HLC3 = 3
    HLC2 = 4
    LOW = 5
    OC2 = 6
    HL = 7

class Strategy():
    '''
    b : balance
    q: volume quota
    msw : Temps d'attente maximum avant vente forcé
    msb : Temps d'attente minimum avant réajustement prix achat
    r : reference de prix pour prix d'achat (ohlc)
    bvd: Variation de référence après achat réussi , en vue d'un krack ou assimilé,
    svd: Variation de référence après vente réussi , en vue d'un krack ou assimilé,
    bvp: Variation de référence après achat réussi , en vue d'un pump ou assimilé,
    svp: Variation de référence après vente réussi , en vue d'un pump ou assimilé,
    '''
    def __init__(self,b,q,msw,mbw,r,svd,bvd,svp,bvp):
        self.balance = b
        self.df2 = pd.DataFrame(columns=["date","Open","High","Low","Close","Volume","entry_date",
                                         "entry_price","exit_price","shares","type","exit_date",
                                         "details","filled","unfilled","total"])
        self.quota = q
        self.ref = r
        self.pips = 1 / 10000
        self.instrument = "USDC"
        self.max_sell_wait = msw
        self.max_buy_wait = mbw
        self.runDate = datetime.datetime.now()
        self.shares = 0
        self.allowPartialSell = False
        self.allowPartialBuy = False
        self.avgVolume = 0
        self.now = datetime.datetime.min
        self.buy_variation_dump = bvd
        self.buy_variation_pump = bvp

    def process(self):
        df1 = self.dataframe_init()
        df1.astype({"exit_price":float})
        sum = 0
        buy_variation_dump = self.buy_variation_dump
        buy_variation_pump = self.buy_variation_pump
        low = 0
        isBuyFilled = True
        isSellFilled = False
        sell_counter = 0
        buy_counter = 0
        positions = []
        last_entry_price = 0        

        for i in df1.index:
            d = df1.iloc[i,0]
            self.now = d
            # o = float(values[1])
            o = df1.iloc[i,1]

            # h = float(values[2])
            h = df1.iloc[i,2]

            l = df1.iloc[i,3]

            c = df1.iloc[i,4]

            # v = float(values[5])
            v = df1.iloc[i,5]

            position = Position(d,o,h,c,l,v)

            
            if len(positions) >= 1 and not isSellFilled:
                position = positions[-1]
                setattr(position,"type","S" if not isBuyFilled else "B")
                
            # entry price
            # e = 0

            ref = self.ref
            # position = self.position
            balance = self.balance
            avgVolume = self.avgVolume
            pips = self.pips
            max_sell_wait = self.max_sell_wait
            max_buy_wait = self.max_buy_wait

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

            if low == 0:
                low = l
                continue
            
            if last_entry_price > 0 and o < (last_entry_price * (1- (buy_variation_dump/100))):          
                send_email(Mail_Subject.BUY_VAR_DUMP)
                exit()

            '''
            if last_exit_price > 0 and o < (last_exit_price * (1- (sell_variation_dump/100))):          
                send_email(Mail_Subject.SELL_VAR_DUMP)
                exit()            
            '''

            if last_entry_price > 0 and o > (last_entry_price * (1 + (buy_variation_pump/100))):          
                send_email(Mail_Subject.BUY_VAR_PUMP)
                exit()            

            '''
            if last_exit_price > 0 and o > (last_exit_price * (1 + (sell_variation_pump/100))):          
                send_email(Mail_Subject.SELL_VAR_PUMP)
                exit()            
            '''

            #VENTE
            if position.get("type") == "B":
                x = last_exit_price
                if e == x:
                    f = position.get('filled')
                    u = position.get('unfilled')                                        
                    t = f + u
                    if v > t:
                            shares = t
                            isSellFilled = True
                            isBuyFilled = False
                            self.manage_filled(shares)                        
                    elif not isSellFilled:
                        shares = u
                        if v < shares:
                            if not self.allowPartialSell:
                                continue                            
                            shares = v
                            self.manage_unfilled(abs(f+v),abs(u-v))
                        else:
                            isSellFilled = True
                            self.manage_filled(shares+f)

                    details = f"VENTE a {x} sur la bougie du {d}"

                    def add_exit(e,d,x):
                        self.dataframe_add("type", "B" if not isSellFilled else "S")
                        self.dataframe_add("exit_price",e)
                        self.dataframe_add("exit_date",d)
                        self.dataframe_add("details",details)
                        self.dataframe_add("shares",u)
                        self.dataframe_add("balance",sum)

                    add_exit(e,d,x)

                    cost = last_entry_price * shares
                    earn = x * shares
                    sum += earn - cost

                    low = l
                    sell_counter = 0

                else:
                    sell_counter += 1
                    if sell_counter > max_sell_wait:
                        sell_counter = 0
                        low = l
                        last_exit_price = low
                        self.manage_forced_sell(low, e)                    
                    else:
                        details = self.do_nothing(d, e, x)

                df1.loc[df1["date"] == d,["details"]] = details
                
                position = self.fill_position_from_series(position,df1.loc[df1["date"] == d].squeeze())
                positions.append(position)


            # ACHAT
            elif position.get("type") == "S":
                if e == low:
                    u = position.get('unfilled')
                    f = position.get('filled')

                    if not isBuyFilled and u != 0 and f != 0:
                        shares = u
                        if v < shares:
                            if not self.allowPartialBuy:
                                return
                            shares = v
                            self.manage_unfilled(abs(f+v),abs(u-v))
                        else:
                            isBuyFilled = True
                            self.manage_filled(shares+f)
                    else:
                        isBuyFilled, shares = self.manage_entry(sum, v, position, balance, e)
                        isSellFilled = False

                    last_entry_price = e
                    last_exit_price = e + pips

                    details = f"ACHAT a {o} sur la bougie du {d}"
                    df1.astype({"entry_price":float})

                    def add_entry(e,d,shares):
                        df1.loc[df1["date"] == d,["details"]] = details
                        df1.loc[df1["date"] == d,["entry_price"]] = e
                        df1.loc[df1["date"] == d,["entry_date"]] = d
                        df1.loc[df1["date"] == d,["exit_price"]] = e+pips
                        df1.loc[df1["date"] == d,["shares"]] = shares
                        df1.loc[df1["date"] == d,["filled"]] = "S" if not isBuyFilled else "B"

                    add_entry(e,d,shares)

                    cost = shares*e
                    balance -= cost - sum
                    buy_counter = 0
                                    
                    position = self.fill_position_from_series(position,df1.loc[df1["date"] == d].squeeze())
                    positions.append(position)

                else:
                    buy_counter += 1
                    if buy_counter > max_buy_wait:
                        buy_counter = 0
                        low = l
                        details = f"REAJUSTEMENT PRIX ACHAT a {low}"
                        df1.loc[df1["date"] == d,["details"]] = details

        df1.to_csv('pit.csv',decimal=",")
        print(positions)
        return sum 

    def manage_entry(self, sum, v, position, balance, e):
        tempshares = (balance + sum) / e
        isBuyFilled = tempshares < v
        position.set('unfilled',abs(tempshares - v))
        shares = min(tempshares,v)
        position.set('filled', shares)
        return isBuyFilled,shares

    def do_nothing(self, d, e, x):
        self.dataframe_add("type", "N")
        self.dataframe_add("entry_date", d)
        self.dataframe_add("entry_price", e)
        self.dataframe_add("exit_price", x)
        details = f"On passe bougie suivante"
        self.dataframe_add("details", details)

    def manage_forced_sell(self, low, e):
        self.dataframe_add('details', f"VENTE FORCE a {low}")
        self.dataframe_add('entry_price',e)
        self.dataframe_add('exit_price',low)

    def manage_filled(self,s):
        self.dataframe_add('unfilled',s)
        self.dataframe_add('filled',0)

    def manage_unfilled(self,f,u):
        self.dataframe_add('filled',f)
        self.dataframe_add('unfilled',u)

    def show(self,sum):
        print(self.balance + sum)
        print(self.avgVolume)

    def dataframe_add(self,setted,value):
        df1 = self.dataframe
        df1.loc[df1["date"] == self.now,[setted]] = value        

    def dataframe_insert(self,pos,values):
        self.df2.concat()

    def dataframe_init(self):
        df1 = pd.read_csv(f'./data/bybit/USDC/data_2D_20230701_1m.csv',delimiter=',')
        self.first_use_case_date = df1.iloc[0,0]
        self.first_use_case_date = datetime.datetime.strptime(str(self.first_use_case_date), '%Y-%m-%d %H:%M:%S').date()        
        df1 = df1.rename(columns={"Date Time":"date"})
        first_use_case_date = 0
        df1["entry_date"] = ""
        df1["entry_price"] = 0
        df1["exit_price"] = 0
        df1["shares"] = ""
        df1["type"] = "RAS"
        df1["exit_date"] = ""
        df1["details"] = ""
        self.avgVolume = df1["Volume"].mean() * self.quota
        self.dataframe = df1
        return self.dataframe

    def dataframe_persist(self):
        self.dataframe.to_csv(f"Report[MAJ{self.runDate}]_FILLED_2D_{self.first_use_case_date}.csv",decimal=',')

    def fill_position_from_array(self,position,arr):
        f = getattr(position,'filled')
        u = getattr(position,'unfilled')
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

s = Strategy(1000,1,30,30,Reference.OPEN,10,10,10,10)
sum = 0
sum = s.process()
s.dataframe_persist()
if (sum is not None):
    s.show(sum)

# print(positions)
