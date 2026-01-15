import ccxt
import pandas as pd
import yfinance as yf

# --- CONFIG ---
crypto_exchange = ccxt.kraken()
timeframe = '1d'  # Changed to daily
limit = 500  # 500 days = ~1.5 years of data (enough for SMA233)

# --- FETCHING FUNCTIONS ---
def fetch_crypto_data(symbol):
    """Fetch daily crypto data from Kraken"""
    ohlcv = crypto_exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('timestamp', inplace=True)
    return df

def fetch_stock_data(ticker):
    """Fetch daily stock data from Yahoo Finance"""
    # Fetch daily data directly
    daily_df = yf.download(ticker, period='2y', interval='1d', progress=False, auto_adjust=True)
    
    if daily_df.empty:
        raise ValueError("No data fetched")
    
    if isinstance(daily_df.columns, pd.MultiIndex):
        daily_df.columns = daily_df.columns.get_level_values(0)
    
    # Rename columns to lowercase for consistency
    daily_df.rename(columns={
        'Close': 'close',
        'Open': 'open',
        'High': 'high',
        'Low': 'low',
        'Volume': 'volume'
    }, inplace=True)
    
    # Reset and rename index
    daily_df.reset_index(inplace=True)
    daily_df.rename(columns={'Date': 'timestamp'}, inplace=True)
    daily_df.set_index('timestamp', inplace=True)
    
    return daily_df