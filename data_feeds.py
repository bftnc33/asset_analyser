import ccxt
import pandas as pd
import yfinance as yf

# --- CONFIG ---
crypto_exchange = ccxt.kraken()
timeframe = '1w'  # Changed to weekly
limit = 300  # 300 weeks = ~6 years of data

# --- FETCHING FUNCTIONS ---
def fetch_crypto_data(symbol):
    """Fetch weekly crypto data from Kraken"""
    ohlcv = crypto_exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('timestamp', inplace=True)
    return df

def fetch_stock_data(ticker):
    """Fetch weekly stock data from Yahoo Finance"""
    # Fetch daily data first, then resample to weekly
    daily_df = yf.download(ticker, period='2y', interval='1d', progress=False, auto_adjust=True)
    
    if daily_df.empty:
        raise ValueError("No data fetched")
    
    if isinstance(daily_df.columns, pd.MultiIndex):
        daily_df.columns = daily_df.columns.get_level_values(0)
    
    # Resample to weekly data (Friday close)
    weekly_df = daily_df.resample('W-FRI').agg({
        'Open': 'first',
        'High': 'max',
        'Low': 'min',
        'Close': 'last',
        'Volume': 'sum'
    }).dropna()
    
    # Rename columns and reset index
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
    
    return weekly_df