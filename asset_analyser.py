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

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as smtp:
            smtp.starttls()
            smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            smtp.send_message(msg)
            print("✅ Email sent successfully.")
    except Exception as e:
        print(f"❌ Failed to send email: {e}")

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

# --- RSI DESCRIPTION ---
def describe_rsi(rsi_value):
    if rsi_value < 30:
        return "RSI OVERSOLD (Potential Buy Signal)"
    elif 30 <= rsi_value < 40:
        return "RSI Near Oversold (Watch for Bounce)"
    elif 40 <= rsi_value <= 60:
        return "RSI Neutral"
    elif 60 < rsi_value <= 70:
        return "RSI Near Overbought (Exercise Caution)"
    else:  # rsi_value > 70
        return "RSI OVERBOUGHT (Potential Sell Signal)"

# --- GENERATE SIGNAL ---
def generate_signal(df):
    latest = df.iloc[-1]
    prev = df.iloc[-2]
    rsi = latest.rsi

    flag = "Bull Flag" if latest.sma7 > latest.sma30 else "Bear Flag"
    trend = "Rising" if latest.close > prev.close else "Falling"
    
    rsi_desc = describe_rsi(rsi)

    return f"{flag} - {trend} | {rsi_desc}"

# --- ANALYZE ASSET ---
def analyze_asset(symbol, df, is_crypto=False, prev_signals=None, new_signals=None, new_alerts=None):
    df = add_indicators(df)
    df.dropna(inplace=True)
    if len(df) < 2:
        print(f"{symbol}: Not enough data.")
        return

    latest = df.iloc[-1]
    sma7 = float(latest['sma7'])
    sma30 = float(latest['sma30'])
    rsi = float(latest['rsi'])
    rsi_desc = describe_rsi(rsi)
    price = float(latest['close'])

    signal = generate_signal(df)
    new_signals[symbol] = signal  # track current signal

    symbol_display = f"{symbol} (Crypto)" if is_crypto else symbol
    currency_symbol = "£" if is_crypto or symbol.endswith('.L') else "$"

    output = (f"\n🔹 {symbol_display}:\n"
              f"   Current Price: {currency_symbol}{price:,.2f}\n"
              f"   SMA7: {currency_symbol}{sma7:,.2f}\n" 
              f"   SMA30: {currency_symbol}{sma30:,.2f}\n"
              f"   RSI: {rsi:.2f}\n"
              f"   Signal: {signal}")
    print(output)

    # Send alert if signal has changed
    if prev_signals.get(symbol) != signal:
        new_alerts.append(output)  # Accumulate alert message

# --- MAIN LOOP ---
if __name__ == "__main__":
    prev_signals = load_previous_signals()
    new_signals = {}
    new_alerts = []  # Collect alerts to send once

    for symbol in crypto_symbols:
        try:
            df = fetch_crypto_data(symbol)
            analyze_asset(symbol, df, is_crypto=True, prev_signals=prev_signals, new_signals=new_signals, new_alerts=new_alerts)
        except Exception as e:
            print(f"Error fetching crypto {symbol}: {e}")

    for ticker in stock_symbols:
        try:
            df = fetch_stock_data(ticker)
            analyze_asset(ticker, df, is_crypto=False, prev_signals=prev_signals, new_signals=new_signals, new_alerts=new_alerts)
        except Exception as e:
            print(f"Error fetching stock {ticker}: {e}")

    # If any alerts were generated, send one combined message
    if new_alerts:
        full_message = "\n\n".join(new_alerts)
        subject = f"📈 Market Signal Updates ({len(new_alerts)} changes)"
        send_email(subject, full_message)
        send_telegram(full_message)

    save_signals(new_signals)
