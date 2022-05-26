#!./stracker/bin/python3
import pandas as pd
from stock_analyzer import  Stockalyzer
import alpaca_trade_api as tradeapi
import sqlite3
import re
from dotenv import load_dotenv
import os
import logging
import json

class Trader:
    def __init__(self, buy_list=None):
        logging.basicConfig(filename='/var/www/html/log/trader.log',
                            format='%(asctime)s %(levelname)-8s %(message)s',
                            level=logging.INFO,
                            datefmt='%Y-%m-%d %H:%M:%S')
        load_dotenv()
        with open("config.json", "r") as f:
            self.params = json.load(f)
        
        self.api = tradeapi.REST(os.getenv('APCA_API_KEY_ID'), os.getenv('APCA_API_SECRET_KEY'), self.params['paper_trading_endpoint'])
        self.account = self.api.get_account()
        self.positions = self.api.list_positions()
        
        if buy_list != None:
            self.buy_list = buy_list
        else:
            db = r"/var/www/html/stockdb.sqlite"
            conn = sqlite3.connect(db)
            df = pd.read_sql('SELECT * FROM stockdb', conn)
            self.buy_list = df.loc[df['Analysis'] == 'Buy']
        self.buy_list = self.buy_list.loc[self.buy_list['Score'] == 8].sort_values(by=['Price'])

    def evalPositions(self):
        orders = []
        for pos in self.positions:
            symbol = pos.symbol.strip()
            s = Stockalyzer(symbol)
            logging.info('{}: {}'.format(symbol, s.get_analysis()))
            if s.get_analysis() != 'Buy':
                orders = self.api.list_orders()
                for order in orders:
                    if order.symbol == symbol:
                        self.api.cancel_order(order.id)
                self.api.submit_order(symbol, qty=pos.qty, side='sell', type='market')
                logging.info('Sold {}'.format(symbol))
                orders.append(symbol)
        return orders

    def buyPositions(self):
        buying_power = float(self.account.buying_power)
        
        if len(self.buy_list.index) == 0:
            logging.info('No stocks found to buy')
            return "No Stocks Found"
        
        total = self.buy_list['Price'].sum()
        orders = []
        
        for i in range(len(self.buy_list.index)):
            stock = self.buy_list.iloc[i]
            fraction = stock['Price'] / total
            s = Stockalyzer(self.buy_list.iloc[i]['Symbol'])
            analysis = s.get_analysis()
            if analysis == 'Buy':
                orders.append(stock['Price'])
                adr = stock['ADR']
                buy_price = round(s.getPrice(), 2)
                tp_price = round(buy_price + adr * 2, 2)
                stop_price = round(buy_price - adr, 2)
                logging.info('Buying:')
                buy_amount = buying_power * fraction
                logging.info(stock)
                
                self.api.submit_order(stock['Symbol'],
                                      notional=buy_amount,
                                      side='buy',
                                      type='market',
                                      time_in_force='day')
    
        return orders
