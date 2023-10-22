import datetime
import itertools
# from pyalgotrade.optimizer import local
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

body = """
        Bonjour,
            Sur une des opérations le gain a été négatif.Ceci mérite peut-être votre attention
            Le processus a été complètement stoppé le temps de l'analyse.
        """
texts['NEGATIVE_GAIN'] = {
    "subject":"Gain négatif lors d'un trade",
    "body":body
}

recipients = ['bentaleb.youness@gmail.com']

msg = MIMEMultipart()
msg['From'] = smtp_username
msg['To'] = ",".join(recipients)

buy_counter = 0
sell_counter = 0
low = 0
last_entry_price = 0
last_exit_price = 0
sum = 0
dataframe = {}

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
    NEGATIVE_GAIN = 5

class Message:

    def __init__(self) -> None:
        pass   

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
        self.buy_variation_dump = bvd
        self.sell_variation_dump = svd
        self.buy_variation_pump = bvp
        self.sell_variation_pump = svp
        self.now = datetime.datetime.min
        self.quota = q
        self.ref = r
        self.checkVolume = not False
        self.pips = 1 / 10000
        self.instrument = "USDC"
        self.sell_counter = 0
        self.buy_counter = 0
        self.max_sell_wait = msw
        self.max_buy_wait = mbw
        self.runDate = datetime.datetime.now()
        # low = 1.0002
        self.shares = 0
        self.sell_counter = 0
        self.buy_counter = 0
        self.position = {"type":"S","entry_price":"","entry_date":"","exit_price":"","exit_date":""}
        self.avgVolume = 0

    def process(self):
        global last_entry_price,last_exit_price,low,sum,dataframe,position
        dataframe = self.dataframe_init()
        ref = self.ref
        # position = self.position
        buy_variation_dump = self.buy_variation_dump
        buy_variation_pump = self.buy_variation_pump

        for i in dataframe.index:            
            d = dataframe.iloc[i,0]
            self.now = d

            # o = float(values[1])
            o = dataframe.iloc[i,1]            

            # h = float(values[2])
            h = dataframe.iloc[i,2]

            l = dataframe.iloc[i,3]

            c = dataframe.iloc[i,4]

            # v = float(values[5])
            v = dataframe.iloc[i,5]

            # entry price
            # e = 0

            e = 0

            e = self.switch_price_reference(ref, o, h, l, c)

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
                        
            if position['type'] == "B":
                low = self.exit_position(position, d, l, e)

            elif position['type'] == "S":        
                self.entry_position(position, d, o, l, v, e)
            
        return sum 

    def switch_price_reference(self, ref, o, h, l, c):
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

    def entry_position(self, position, d, o, l, v, e):
        global buy_counter,last_entry_price,last_exit_price,sum,dataframe,low
        if e == low:
            shares = (self.balance + sum) / e
            if not self.checkVolume or v >= shares:
                details = f"ACHAT a {o} sur la bougie du {d}"
                dataframe.astype({"entry_price":float})
                
                def add_entry(e,d,shares):
                    self.dataframe_add("details",details)
                    self.dataframe_add("entry_price",e)
                    self.dataframe_add("entry_date",d)
                    self.dataframe_add("exit_price",e+self.pips)
                    self.dataframe_add("shares",shares)
                    self.dataframe_add("type","B")                                       

                add_entry(e,d,shares)


                position["type"] = "B"
                position["exit_date"] = ""
                position["entry_date"] = d
                position["entry_price"] = e
                last_entry_price = e
                position["shares"] = (self.balance + sum) / e
                position["exit_price"] = e+self.pips
                last_exit_price = e+self.pips
                buy_counter = 0
            else:
                self.dataframe_add("details",f"Pas assez de volume pour acheter")
                buy_counter += 1
        else:
            buy_counter += 1
            if buy_counter > self.max_buy_wait:
                buy_counter = 0
                low = l
                self.dataframe_add("details",f"REAJUSTEMENT PRIX ACHAT a {low}")
            else:
                self.dataframe_add("type",f"N")
                self.dataframe_add("entry_date",d)
                self.dataframe_add("details",f"On passe bougie suivante")
        

    def exit_position(self, position, d, l, e):
        global sell_counter,sum
        global low
        x = position["exit_price"]
        if e == x:
            s = position["shares"]
            if not self.checkVolume or s<=self.avgVolume:
                dataframe.astype({"exit_price":float})

                def add_exit(e,d,x):
                    self.dataframe_add("type", "S")
                    self.dataframe_add("exit_price",e)
                    self.dataframe_add("exit_date",d)
                    self.dataframe_add("details",f"VENTE a {x} sur la bougie du {d}")
                    self.dataframe_add("shares",s)
                    self.dataframe_add("balance",sum)

                add_exit(e,d,x)

                position["type"] = "S"
                p = position['entry_price']
                cost = p*s
                        
                position["exit_date"] = d
                position["exit_price"] = e
                last_exit_price = e
                earn = e*s
                        
                sum += earn - cost

                if sum < -1:
                    send_email(Mail_Subject.NEGATIVE_GAIN)
                    exit()

                        # if (earn < cost): print(balance+oldsum,balance+sum)

                position['balance'] = sum
                position["shares"] = 0
                low = l
                sell_counter = 0 
            else:
                self.dataframe_add("details",f"Pas assez de volume pour vendre")
                sell_counter += 1

        else:
            sell_counter += 1
            if sell_counter > self.max_sell_wait:
                sell_counter = 0
                low = l
                position["exit_price"] = low
                self.dataframe_add("exit_price",low)
                self.dataframe_add("details",f"VENTE FORCE a {low}")            
            else:
                self.dataframe_add("type",f"N")
                self.dataframe_add("entry_date",d)
                self.dataframe_add("details",f"On passe bougie suivante")
        return low      

    def show(self,sum):
        print(self.balance + sum)
        print(self.avgVolume)
        print(str((sum/self.balance) * 100),'%')

    def dataframe_add(self,setted,value):
        df1 = self.dataframe
        df1.loc[df1["date"] == self.now,[setted]] = value        




    def dataframe_load(self,path):
        df1 = pd.read_csv(path)
        self.first_use_case_date = df1.iloc[0,0]
        self.first_use_case_date = datetime.datetime.strptime(str(self.first_use_case_date), '%Y-%m-%d %H:%M:%S').date()        
        df1 = df1.rename(columns={"Date Time":"date"})
        first_use_case_date = 0
        df1["entry_date"] = ""
        df1["entry_price"] = 0
        df1["exit_price"] = 0
        df1["shares"] = ""
        df1["type"] = "N"
        df1["exit_date"] = ""
        df1["details"] = ""
        self.avgVolume = df1["Volume"].mean() * self.quota
        self.dataframe = df1
        return self.dataframe

    def dataframe_persist(self):
        self.dataframe.to_csv(f"Report[MAJ{self.runDate}]_FILLED_2D_{self.first_use_case_date}.csv",decimal=',')

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


s = Strategy(1000,1,30,30,Reference.OPEN,10,10,10,10)
sum = 0
sum = s.process()
s.dataframe_persist()
s.show(sum)

# print(positions)
