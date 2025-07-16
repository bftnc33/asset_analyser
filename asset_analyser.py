import os
import pandas as pd
import ta
import ccxt
import yfinance as yf
import smtplib
import requests
import json
from email.message import EmailMessage
from dotenv import load_dotenv

# --- LOAD ENVIRONMENT VARIABLES ---
load_dotenv()

EMAIL_ADDRESS = os.getenv('EMAIL_ADDRESS')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')
SMTP_SERVER = os.getenv('SMTP_SERVER')
SMTP_PORT = int(os.getenv('SMTP_PORT', 587))
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# --- CONFIG ---
stock_symbols = ['MSTR', 'NVDA', 'VUAG.L', 'COFF.L', 'SGLN.L']
crypto_symbols = ['BTC/GBP', 'ETH/GBP', 'XRP/GBP', 'SOL/GBP', 'ADA/GBP', 'XLM/GBP', 'SAND/GBP', 'DOGE/GBP', 'SUI/GBP', 'LINK/GBP', 'LTC/GBP']
crypto_exchange = ccxt.kraken()
timeframe = '1d'
limit = 100
SIGNAL_FILE = "signals.json"

def load_previous_signals():
    if os.path.exists(SIGNAL_FILE):
        with open(SIGNAL_FILE, "r") as f:
            return json.load(f)
    return {}

def save_signals(signals):
    with open(SIGNAL_FILE, "w") as f:
        json.dump(signals, f, indent=2)

# --- EMAIL FUNCTION ---
def send_email(subject, body):
    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = EMAIL_ADDRESS
    msg['To'] = EMAIL_ADDRESS
    msg.set_content(body)

    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as smtp:
        smtp.starttls()
        smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        smtp.send_message(msg)

def send_telegram(message):
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML"  # optional
    }

    response = requests.post(url, data=payload)
    response.raise_for_status()

# --- FETCH FUNCTIONS ---
def fetch_crypto_data(symbol):
    ohlcv = crypto_exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    return df

def fetch_stock_data(ticker):
    df = yf.download(ticker, period='100d', interval='1d', progress=False, auto_adjust=True)

    if df.empty:
        raise ValueError("No data fetched")

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df.reset_index(inplace=True)
    df.rename(columns={
        'Date': 'timestamp',
        'Close': 'close',
        'Open': 'open',
        'High': 'high',
        'Low': 'low',
        'Volume': 'volume'
    }, inplace=True)
    return df

# --- ADD INDICATORS ---
def add_indicators(df):
    df['sma7'] = ta.trend.sma_indicator(df['close'], window=7)
    df['sma30'] = ta.trend.sma_indicator(df['close'], window=30)
    df['rsi'] = ta.momentum.rsi(df['close'], window=14)
    return df

# --- PRICE ACTION HELPERS ---
def is_bullish_engulfing(prev, latest):
    return (prev['close'] < prev['open'] and
            latest['close'] > latest['open'] and
            latest['close'] > prev['open'] and
            latest['open'] < prev['close'])

def is_bearish_engulfing(prev, latest):
    return (prev['close'] > prev['open'] and
            latest['close'] < latest['open'] and
            latest['open'] > prev['close'] and
            latest['close'] < prev['open'])

def wick_analysis(row):
    upper_wick = row['high'] - max(row['open'], row['close'])
    lower_wick = min(row['open'], row['close']) - row['low']
    body = abs(row['close'] - row['open'])

    if lower_wick > 2 * body:
        return 'LONG LOWER WICK (BUYING PRESSURE)'
    elif upper_wick > 2 * body:
        return 'LONG UPPER WICK (SELLING PRESSURE)'
    return None

# --- GENERATE SIGNAL ---
def generate_signal(df):
    latest = df.iloc[-1]
    prev = df.iloc[-2]
    rsi = latest.rsi

    bullish_engulf = is_bullish_engulfing(prev, latest)
    bearish_engulf = is_bearish_engulfing(prev, latest)
    wick_info = wick_analysis(latest)

    if bullish_engulf and rsi < 70:
        if latest.sma7 > latest.sma30:
            return '🚀 BULLISH ENGULFING REVERSAL (STRONG BUY)'
        else:
            return '🚀 BULLISH ENGULFING - (WAIT)'

    if bearish_engulf and rsi > 30:
        return '⚠️ BEARISH ENGULFING REVERSAL (STRONG SELL)'

    if latest.sma7 > latest.sma30:
        if latest.close > prev.close:
            if 50 <= rsi < 70:
                return '📈 BULL FLAG: SWEET SPOT (BUY)'
            elif rsi >= 70:
                return '📈 BULL FLAG: OVERBOUGHT (SELL)'
        else:
            if 50 <= rsi < 70:
                return '📉 BULL FLAG: FALLING (WAIT)'
            elif rsi >= 70:
                return '📉 BULL FLAG: FALLING & OVERBOUGHT (SELL)'
    elif latest.sma30 > latest.sma7:
        if latest.close > prev.close:
            if 30 < rsi < 50:
                return '📉 BEAR FLAG: POTENTIAL REVERSAL (WAIT)'
            elif rsi <= 30:
                return '📉 BEAR FLAG: OVERSOLD (BUY)'
        else:
            if 30 < rsi < 50:
                return '📉 BEAR FLAG: FALLING (WAIT)'
            elif rsi <= 30:
                return '📉 BEAR FLAG: OVERSOLD & DROPPING (WAIT)'

    return wick_info or '🤷‍♂️ NO CLEAR SIGNAL'

# --- ANALYZE ASSET ---
def analyze_asset(symbol, df, is_crypto=False, prev_signals=None, new_signals=None):
    df = add_indicators(df)
    df.dropna(inplace=True)
    if len(df) < 2:
        print(f"{symbol}: Not enough data.")
        return

    latest = df.iloc[-1]
    sma7 = float(latest['sma7'])
    sma30 = float(latest['sma30'])
    rsi = float(latest['rsi'])
    price = float(latest['close'])

    signal = generate_signal(df)
    new_signals[symbol] = signal  # track current signal

    symbol_display = f"{symbol} (Crypto)" if is_crypto else symbol
    currency_symbol = "£" if is_crypto or symbol.endswith('.L') else "$"

    output = (f"\n🔹 {symbol_display}:\n"
              f"   Price: {currency_symbol}{price:,.2f}\n"
              f"   SMA7: {currency_symbol}{sma7:,.2f} | SMA30: {currency_symbol}{sma30:,.2f} | RSI: {rsi:.2f}\n"
              f"   Signal: {signal}")
    print(output)

    # Send alert if signal has changed
    if prev_signals.get(symbol) != signal:
        subject = f"{symbol} Signal Changed: {signal}"
        send_email(subject, output)
        send_telegram(output)

# --- MAIN LOOP ---
if __name__ == "__main__":
    prev_signals = load_previous_signals()
    new_signals = {}

    for symbol in crypto_symbols:
        try:
            df = fetch_crypto_data(symbol)
            analyze_asset(symbol, df, is_crypto=True, prev_signals=prev_signals, new_signals=new_signals)
        except Exception as e:
            print(f"Error fetching crypto {symbol}: {e}")

    for ticker in stock_symbols:
        try:
            df = fetch_stock_data(ticker)
            analyze_asset(ticker, df, is_crypto=False, prev_signals=prev_signals, new_signals=new_signals)
        except Exception as e:
            print(f"Error fetching stock {ticker}: {e}")

    save_signals(new_signals)
