import ccxt
import pandas as pd
import yfinance as yf
from datetime import datetime, timezone, date, timedelta

# --- CONFIG ---
crypto_exchange = ccxt.kraken()
timeframe = '1w'
limit = 500

# --- FETCHING FUNCTIONS ---

def fetch_crypto_data(symbol):
    """
    Fetch weekly crypto data from Kraken.

    Drops any candle from the current week (UTC) since it is not yet
    complete. The most recent row will always be last week's fully
    closed candle.
    """
    ohlcv = crypto_exchange.fetch_ohlcv(
        symbol, timeframe=timeframe, limit=limit
    )
    df = pd.DataFrame(
        ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
    )
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
    df.set_index('timestamp', inplace=True)

    # Drop the current week's incomplete candle
    today = pd.Timestamp.now(tz='UTC').normalize()
    start_of_week = today - pd.Timedelta(days=today.dayofweek)
    df = df[df.index < start_of_week]

    return df


def fetch_stock_data(ticker):
    """
    Fetch weekly stock data from Yahoo Finance.

    Drops the current week's candle since it is not yet complete.
    The most recent row will always be last week's fully closed candle.
    """
    weekly_df = yf.download(
        ticker, period='5y', interval='1wk', progress=False, auto_adjust=True
    )

    if weekly_df.empty:
        raise ValueError("No data fetched")

    if isinstance(weekly_df.columns, pd.MultiIndex):
        weekly_df.columns = weekly_df.columns.get_level_values(0)

    weekly_df.rename(columns={
        'Close': 'close',
        'Open': 'open',
        'High': 'high',
        'Low': 'low',
        'Volume': 'volume'
    }, inplace=True)

    weekly_df.reset_index(inplace=True)
    weekly_df.rename(columns={'Date': 'timestamp'}, inplace=True)
    weekly_df.set_index('timestamp', inplace=True)

    # Drop the current week's incomplete candle
    today = date.today()
    start_of_week = today - timedelta(days=today.weekday())
    df_dates = weekly_df.index.map(
        lambda x: x.date() if hasattr(x, 'date') else x
    )
    weekly_df = weekly_df[df_dates < start_of_week]

    return weekly_df