# trade simulations using delta bsi signals with bb/std dev entries

import numpy as np
import pandas as pd
from hmmlearn import hmm
from binance.client import Client
from sqlalchemy import create_engine
from util.bsi_labeler import HawkesBSI
from util.send_message import send_message


def main():
    trade_symbol = 'XTZUSDT'
    ### read position from rdb ###
    engine = create_engine('postgresql://kumprj:hydepark1@test-db-first-try.cnxdgopof2w9.us-east-2.rds.amazonaws.com:5432/myFirstDatabase')
    position_df = pd.read_sql('xtzusdtposition', engine)
    position = position_df['position'][0]
    print(position)

    # empty dataframe for positions
    record_positions = pd.DataFrame(columns = ['time', 'price', 'trade_dir', 'entry', 'symbol'])

    ### get binance candle data ###
    api_key = 'WpKjVWgdBjoHqEQOiZwydPhcSPilbfUAbd8IjWxA15xlnONht0gEwWQd2j2xHhPg'
    secret_key = 'Mz36N8O5xjOgVvjKg00aN4WfzUMh7NW7OBxpoHZXB4JVi5zlWNsIHniyuEOWNItO'
    client = Client(api_key, secret_key)

    candles = client.get_historical_klines(trade_symbol, Client.KLINE_INTERVAL_5MINUTE, "1 days ago UTC")
    price_df = pd.DataFrame(candles, columns=[
        'time', 'open', 'high', 'low', 
        'close', 'volume','Close time', 
        'Quote asset volume', 'Number of trades',
        'buyvol',
        'Taker buy quote asset volume', 'Ignore'
        ])

    price_df = price_df[:-1] # remove last incomplete candle 

    # resample to 10T
    price_df.index = pd.to_datetime(price_df['time'], unit='ms') # TODO: remove candle that's inprogress? 
    price_df = price_df.apply(pd.to_numeric)
    price_df = price_df.resample('10T').agg({'open': 'first',
                                            'high': 'max',
                                            'low': 'min',
                                            'close': 'last',
                                            'volume': 'sum',
                                            'buyvol': 'sum'})


    price_df['sellvol'] = price_df['volume'] - price_df['buyvol']

    ### Trade signals ###
    # label data with bsi
    kappa = 0.05
    obj = HawkesBSI(kappa)
    bsi_df = obj.eval(price_df)


    # calc trade signals
    lookback = 100
    bb_std = 4
    exit_thresh = -0.25
    bsi_df['delta_bsi'] = bsi_df['bsi'].diff(10)
    bsi_df['ewm'] = bsi_df['delta_bsi'].ewm(span=lookback).mean()
    bsi_df['stdvol'] = bsi_df['delta_bsi'].rolling(lookback).std()
    bsi_df['upper_band'] = bsi_df['ewm']  + (bb_std * bsi_df['stdvol'])
    bsi_df['lower_band'] = bsi_df['ewm']  - (bb_std * bsi_df['stdvol'])

    long_sig_thresh = bsi_df['lower_band'].iloc[-1]
    short_sig_thresh = bsi_df['upper_band'].iloc[-1]


    # trade signal entry
    if bsi_df['delta_bsi'].iloc[-1] <= long_sig_thresh:
        trade_sig = 1
    elif bsi_df['delta_bsi'].iloc[-1] >= short_sig_thresh:
        trade_sig = -1
    else:
        trade_sig = 0

    # exit signals
    long_exit = np.where(bsi_df['delta_bsi'].iloc[-1] > (exit_thresh * long_sig_thresh), 1, 0)
    short_exit = np.where(bsi_df['delta_bsi'].iloc[-1] < (exit_thresh * short_sig_thresh), 1, 0)

    ### Position updating/recording ###
    # get current depth for sim prices
    depth = client.get_order_book(symbol=trade_symbol)
    book_df = pd.DataFrame(depth)
    best_ask = book_df['asks'].iloc[0]
    best_bid = book_df['bids'].iloc[0]

    # exit current position on signals
    if position == 1 and long_exit == 1:
        record_positions = record_positions.append({'time' : pd.datetime.now(), 'price' : best_bid[0], 'trade_dir': -1, 'entry': 0, 'symbol': trade_symbol}, ignore_index=True)
        position = 0
        message = f"Exiting long position on {trade_symbol}. Price is {best_bid[0]}."
        send_message(message)
    elif position == -1 and short_exit == 1:
        record_positions = record_positions.append({'time' : pd.datetime.now(), 'price' : best_ask[0], 'trade_dir': 1, 'entry': 0, 'symbol': trade_symbol}, ignore_index=True)
        position = 0
        message = f"Exiting short position on {trade_symbol}. Price is {best_ask[0]}."
        send_message(message)

    # open new positions on signals
    if position == 0 and trade_sig == 1:
        record_positions = record_positions.append({'time' : pd.datetime.now(), 'price' : best_ask[0], 'trade_dir': 1, 'entry': 1, 'symbol': trade_symbol}, ignore_index=True)
        position = 1
        message = f"Entering long position on {trade_symbol}. Price is {best_ask[0]}."
        send_message(message)
    elif position == 0 and trade_sig == -1:
        record_positions = record_positions.append({'time' : pd.datetime.now(), 'price' : best_bid[0], 'trade_dir': -1, 'entry': 1, 'symbol': trade_symbol}, ignore_index=True)
        position = -1
        message = f"Entering short position on {trade_symbol}. Price is {best_bid[0]}."
        send_message(message)


    ### write position to rdb ###
    position_df['position'] = position
    position_df.to_sql('xtzusdtposition', engine, schema='public', index=False, if_exists='replace')

    ### write to position tracking rdb ###
    record_positions.to_sql('simTradeTrack', engine, schema='public', index=False, if_exists='append')


# Handler
def lambda_handler(event, context):
    main()
