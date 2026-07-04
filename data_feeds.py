import ccxt
import pandas as pd
import yfinance as yf
from datetime import datetime, timezone, date

# --- CONFIG ---
crypto_exchange = ccxt.kraken()
timeframe = '1d'
limit = 500

# --- FETCHING FUNCTIONS ---

def fetch_crypto_data(symbol):
    """
    Fetch daily crypto data from Kraken.

    Drops any candle from today (UTC) since at 8am the daily candle is only
    8 hours old and not yet complete. The most recent row will always be
    yesterday's fully closed candle.
    """
    ohlcv = crypto_exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
    df.set_index('timestamp', inplace=True)

    # Drop today's incomplete candle
    today = pd.Timestamp.now(tz='UTC').normalize()
    df = df[df.index < today]

    return df


def fetch_stock_data(ticker):
    """
    Fetch daily stock data from Yahoo Finance.

    Drops today's row since at 8am UTC markets haven't opened yet and
    yfinance may include a partial/empty candle for the current day.
    The most recent row will always be yesterday's fully closed candle.
    """
    daily_df = yf.download(ticker, period='2y', interval='1d', progress=False, auto_adjust=True)

    if daily_df.empty:
        raise ValueError("No data fetched")

    if isinstance(daily_df.columns, pd.MultiIndex):
        daily_df.columns = daily_df.columns.get_level_values(0)

    daily_df.rename(columns={
        'Close': 'close',
        'Open': 'open',
        'High': 'high',
        'Low': 'low',
        'Volume': 'volume'
    }, inplace=True)

    daily_df.reset_index(inplace=True)
    daily_df.rename(columns={'Date': 'timestamp'}, inplace=True)
    daily_df.set_index('timestamp', inplace=True)

    # Drop today's incomplete/empty candle
    today = pd.Timestamp.now(tz='UTC').normalize().date()
    df_dates = daily_df.index.map(lambda x: x.date() if hasattr(x, 'date') else x)
    daily_df = daily_df[df_dates < today]

    return daily_df