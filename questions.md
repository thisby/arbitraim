Possibles failles

* arrondissemnt de l'achat +
* fréquence de passage ---
* variation trop importante ---

Q1 : Pourquoi on achète pas immédiatement après avoir vendu?

Get orders:
    $..trades[*].orders

Backtest sur 1 heure (ici 01082023 de 1H a 2H)
    strategy="FREQTRADE";base="DAI";filename="1H_20230801 01H00M00S_${strategy}_${base}_1pips_1m@1m_SL99";freqtrade backtesting -c ../Keep/conf_bybit_usd.json --userdir . --timerange 1690851600-1690855200 --export trades -s SimpleTradeStrategy --fee 0 --pairs ${base}/USDT --export-filename=./backtest_results/input/${filename}.json > ./backtest_results/${filename}.log;filename="";base=""

Backtest sur 1 journée variabilisé:
    strategy="FREQTRADE";base="DAI";filename="1D_20230813_${strategy}_${base}_1pips_1m@1m_SL99";freqtrade backtesting -c ../Keep/conf_bybit_usd.json --userdir . --timerange 20230813-20230814 --export trades -s SimpleTradeStrategy --fee 0 --pairs ${base}/USDT --export-filename=./backtest_results/input/${filename}.json > ./backtest_results/${filename}.log;filename="";base=""

Backtest sur 1 mois (ici Juillet 2023)
    strategy="FREQTRADE";base="DAI";filename="1M_20230701_${strategy}_${base}_1pips_1m@1m_SL99";freqtrade backtesting -c ../Keep/conf_bybit_usd.json --userdir . --timerange 20230701-20230731 --export trades -s SimpleTradeStrategy --fee 0 --pairs ${base}/USDT --export-filename=./backtest_results/input/${filename}.json > ./backtest_results/${filename}.log;filename="";base=""    

Backtest sur 1 an (ici a partir du 19 Aout 2022)
    strategy="FREQTRADE";base="DAI";filename="1A_20220801_${strategy}_${base}_1pips_1m@1m_SL99";freqtrade backtesting -c ../Keep/conf_bybit_usd.json --userdir . --timerange 20220801- --export trades -s SimpleTradeStrategy --fee 0 --pairs ${base}/USDT --export-filename=./backtest_results/input/${filename}.json > ./backtest_results/${filename}.log;filename="";base=""

Force debug
strategy="FREQTRADE";base="DAI";filename="1D_20230307_${strategy}_${base}_1pips_1m@1m_SL99";freqtrade backtesting -c /home/dev/Documents/Dev/Keep/conf_bybit_usd.json --userdir . --timerange 20230307-20230308 --export trades --strategy-path /home/dev/Documents/Dev/trades/strategies -s SimpleTradeStrategy --fee 0 --pairs ${base}/USDT --export-filename=./backtest_results/input/${filename}.json

Q2: Exit signal?

Q3: 


SOLUTIONS POUR STRATEGIE

A - Au 1er trade, Instanciation du prix d'achat a OC2[-1]
B - Si au bout de 30m pas d'achat possible, réévaluation du prix d'achat a OC2[-1]
C - Vente si variation d'1 pips
D - Instanciation du prix d'achat a low de la bougie précédente (donc bougie ou on a vendu)
E - Si au bout de 30m pas d'achat possible, réévaluation du prix d'achat a low[-1]
On repart a C


A - Au 1er trade, Instanciation du prix d'achat a OC2[-1]
    Init,ou populate_indicator sans utiliser le process_new_candles flag
    init ne connait pas dataframe X
    populate_indicator passe sur toutes les bougies il faut donc arriver a lui dire, qu'au premier passage, le prix de reference c'est oc2[-1]
        1 Comment determiner qu'on est au premier passage?

1 Determiner qu'on est au 1er passage
    1 booleen
    1 variable de dataframe natif
    changer la valeur pour tous les elements d'une requete dataframe en particulier?
    en se basant sur la date
        Comment récupérer la date du dataframe? en se basant sur le premier champs


    
Todo : ajouter col vol echangé
vendre si + haut?
    vendre au prix ou l'on a acheté
        vendre au prix le plus bas au bout de 30mn

    
on ne prends que le low...
Volume d'achat

ISSUE 0001:pourquoi pas achat L213
ISSUE 0002:pourquoi pas achat L788
faire apparaitre O H L C
2 simulations une identique
une avec allowpartiallyfilled a true
arrondi des amount


ISSUE 0003: Ajoute la date d'execution de l'achat
ISSUE 0004: pas besoin de tester si prix d'entrée == prix d'ouverture de la bougie pour 
ISSUE 0005: pas besoin de tester si prix de sortie == prix d'ouverture de la bougie pour vendre bn,klpo;Î îj,unybgt(frgbhnj,uikolm:!ùacheter
ISSUE 0006: etre plus précis sur les volumes et les prix de vente ou d'achat
ISSUE 0007: Acheter au prix fixé, pas d'ordre limite


achat de 1000 parts
    => 100 OK, reste 900

    2 cas
        soit v > 900 => filled
        soit v < 900 ==> partial

        si v > 900 ==> RAS
        si v < 900 , remaining = v - 900, et part a acheter == 900