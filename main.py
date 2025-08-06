import os
import json
import logging
import pandas as pd
import ta
import ccxt
import yfinance as yf
import smtplib
import requests
from email.message import EmailMessage
from dotenv import load_dotenv

# --- Setup Logging ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# --- LOAD ENVIRONMENT VARIABLES ---
load_dotenv()

EMAIL_ADDRESS = os.getenv('EMAIL_ADDRESS')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')
SMTP_SERVER = os.getenv('SMTP_SERVER')
SMTP_PORT = int(os.getenv('SMTP_PORT', 587))
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# --- CONFIG ---
SIGNAL_FILE = "signals.json"
crypto_exchange = ccxt.kraken()
timeframe = '1d'
limit = 100

# --- LOAD SYMBOLS ---
def load_symbols(file_path="symbols.json"):
    with open(file_path, "r") as f:
        data = json.load(f)
    return data.get("stocks", []), data.get("crypto", [])

stock_symbols, crypto_symbols = load_symbols()

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
    msg.set_content("This email requires an HTML-capable viewer.")
    msg.add_alternative(body, subtype='html')

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as smtp:
            smtp.starttls()
            smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            smtp.send_message(msg)
        logging.info("✅ Email sent successfully.")
    except Exception as e:
        logging.error(f"❌ Failed to send email: {e}")

def send_telegram(message):
    MAX_LENGTH = 4096
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    # Truncate if too long
    if len(message) > MAX_LENGTH:
        message = message[:MAX_LENGTH - 50] + "\n... (message truncated)"

    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }

    try:
        response = requests.post(url, data=payload)
        response.raise_for_status()
        print("✅ Telegram alert sent.")
    except requests.exceptions.RequestException as e:
        print(f"❌ Failed to send Telegram alert: {e}")
        print(f"🛠️ Payload preview: {payload}")

# --- FETCHING FUNCTIONS ---
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

# --- INDICATORS ---
def add_indicators(df):
    df['sma7'] = ta.trend.sma_indicator(df['close'], window=7)
    df['sma30'] = ta.trend.sma_indicator(df['close'], window=30)
    df['rsi'] = ta.momentum.rsi(df['close'], window=14)
    df['vol_avg'] = df['volume'].ewm(span=20, adjust=False).mean()
    return df

# --- RSI DESCRIPTION ---
def describe_rsi(rsi_value):
    if rsi_value < 30:
        return "🟢 RSI OVERSOLD (Consider Buying)"
    elif rsi_value < 40:
        return "🟡 RSI Near Oversold (Monitor)"
    elif rsi_value <= 60:
        return "⚪️ RSI Neutral"
    elif rsi_value <= 70:
        return "🟡 RSI Near Overbought (Monitor)"
    else:
        return "🔴 RSI OVERBOUGHT (Consider Selling)"

# --- SIGNAL GENERATION ---
def generate_signal(df, latest, prev, rsi_desc):
    sma7, sma30 = latest.sma7, latest.sma30
    prev_sma7, prev_sma30 = prev.sma7, prev.sma30

    flag = "📈 Bull Flag" if sma7 > sma30 else "📉 Bear Flag"
    trend = "🔼 Rising" if latest.close > prev.close else "🔽 Falling"
    price_vs_sma7 = "✅ Price ABOVE SMA7" if latest.close > sma7 else "🔻 Price BELOW SMA7" 
    price_vs_sma30 = "✅ Price ABOVE SMA30" if latest.close > sma30 else "🔻 Price BELOW SMA30"

    crossover = ""
    if prev_sma7 < prev_sma30 and sma7 > sma30:
        crossover = "✨ Golden Cross (SMA7 ↑ SMA30)"
    elif prev_sma7 > prev_sma30 and sma7 < sma30:
        crossover = "⚠️ Death Cross (SMA7 ↓ SMA30)"

    spike_ratio = latest.volume / latest.vol_avg if latest.vol_avg else 0
    volume_spike = ""
    if spike_ratio > 2:
        volume_spike = "📊 Volume Spike: 🚨 Severe"
    elif spike_ratio > 1.5:
        volume_spike = "📊 Volume Spike: ⚠️ Moderate"
    elif spike_ratio > 1.2:
        volume_spike = "📊 Volume Spike: ⚪️ Mild"

    rsi_change = latest.rsi - prev.rsi
    rsi_momentum = ""
    if abs(rsi_change) > 5:
        direction = "↗️ Accelerating" if rsi_change > 0 else "↘️ Decelerating"
        rsi_momentum = f"RSI {direction}"

    parts = [flag, trend, price_vs_sma7, price_vs_sma30]  # Added price_vs_sma30
    if crossover:
        parts.append(crossover)
    if volume_spike:
        parts.append(volume_spike)
    parts.append(rsi_desc)
    if rsi_momentum:
        parts.append(rsi_momentum)

    return " | ".join(parts)

# --- DIFFERENCE CHECK ---
def diff_signal_parts(old_signal, new_signal):
    if not old_signal:
        return new_signal

    def extract_items(text):
        # Clean any existing changes info
        clean_text = text.split("↪️ Changes:")[0].strip() if "↪️ Changes:" in text else text
        return [part.strip() for part in clean_text.split("|") if part.strip()]

    old_items = set(extract_items(old_signal))
    new_items_list = extract_items(new_signal)
    new_items_set = set(new_items_list)

    added = new_items_set - old_items
    removed = old_items - new_items_set

    # Build signal with (was: old_value) for changed items
    enhanced_signal_parts = []
    
    for new_item in new_items_list:
        enhanced_part = new_item
        
        # Check if this new item replaces an old one (same category)
        for old_item in removed:
            # Check for similar categories that should show "was:" format
            if (('Bull Flag' in new_item or 'Bear Flag' in new_item) and ('Bull Flag' in old_item or 'Bear Flag' in old_item)) or \
               (('Rising' in new_item or 'Falling' in new_item) and ('Rising' in old_item or 'Falling' in old_item)) or \
               (('ABOVE SMA7' in new_item or 'BELOW SMA7' in new_item) and ('ABOVE SMA7' in old_item or 'BELOW SMA7' in old_item)) or \
               (('ABOVE SMA30' in new_item or 'BELOW SMA30' in new_item) and ('ABOVE SMA30' in old_item or 'BELOW SMA30' in old_item)) or \
               (('RSI' in new_item and 'RSI' in old_item)):
                enhanced_part = f"{new_item} (was: {old_item})"
                break
        
        enhanced_signal_parts.append(enhanced_part)
    
    return " | ".join(enhanced_signal_parts)

# --- FORMAT OUTPUT ---
def format_output(symbol, latest, previous, signal, rsi_desc, is_crypto, changes=None):
    # Determine currency and formatting
    if symbol.endswith("SGLN.L"):
        currency = "£"
        suffix = ""
        # Convert pence to pounds by dividing by 100
        current_close = latest.close / 100
        previous_close = previous.close / 100
        sma7 = latest.sma7 / 100
        sma30 = latest.sma30 / 100
        price_fmt = "{:,.4f}" if current_close < 1 else "{:,.2f}"
    elif symbol.endswith(".L"):
        currency = "£"
        suffix = ""
        price_fmt = "{:,.4f}" if latest.close < 1 else "{:,.2f}"
        current_close = latest.close
        previous_close = previous.close
        sma7 = latest.sma7 / 100
        sma30 = latest.sma30 / 100
    elif is_crypto:
        # Crypto in GBP
        currency = "£"
        suffix = ""
        price_fmt = "{:,.4f}" if latest.close < 1 else "{:,.2f}"
        current_close = latest.close
        previous_close = previous.close
        sma7 = latest.sma7
        sma30 = latest.sma30
    else:
        # US stocks in USD
        currency = "$"
        suffix = ""
        price_fmt = "{:,.4f}" if latest.close < 1 else "{:,.2f}"
        current_close = latest.close
        previous_close = previous.close
        sma7 = latest.sma7
        sma30 = latest.sma30
    
    price_change = ((current_close - previous_close) / previous_close) * 100
    change_color = "🟢" if price_change > 0 else "🔴" if price_change < 0 else "⚪️"
    
    # Clean the signal first - remove any existing changes line
    clean_signal = signal
    if "↪️ Changes:" in signal:
        clean_signal = signal.split("↪️ Changes:")[0].strip()
    
    # Split signal elements and put each on a new line
    signal_parts = clean_signal.split(' | ')
    formatted_signal = '\n'.join([f"     {part.strip()}" for part in signal_parts if part.strip()])
    
    return (f"\n🔹 {symbol} ({'Crypto' if is_crypto else 'Stock'}):\n"
            f"   Current Price: {currency}{price_fmt.format(current_close)}{suffix}\n"
            f"   Yesterday's Close: {currency}{price_fmt.format(previous_close)}{suffix}\n"
            f"   Price Change: {change_color} {price_change:+.2f}%\n"
            f"   SMA7: {currency}{price_fmt.format(sma7)}{suffix}\n"
            f"   SMA30: {currency}{price_fmt.format(sma30)}{suffix}\n"
            f"   RSI: {latest.rsi:.2f}\n"
            f"   Signal:\n{formatted_signal}")

# --- ANALYZE ASSET ---
def analyze_asset(symbol, df, is_crypto, prev_signals, new_signals, new_alerts):
    df = add_indicators(df)
    df.dropna(inplace=True)
    if len(df) < 2:
        logging.warning(f"{symbol}: Not enough data.")
        return

    latest, prev = df.iloc[-1], df.iloc[-2]
    rsi_desc = describe_rsi(latest.rsi)
    new_signal_raw = generate_signal(df, latest, prev, rsi_desc)

    old_signal = prev_signals.get(symbol)
    full_signal = diff_signal_parts(old_signal, new_signal_raw)

    # Always store the raw signal for next time (not the diffed one)
    new_signals[symbol] = new_signal_raw
    output = format_output(symbol, latest, prev, full_signal, rsi_desc, is_crypto)
    logging.info(output)

    if old_signal != new_signal_raw:
        new_alerts.append(output)

# --- MAIN LOOP ---
if __name__ == "__main__":
    prev_signals = load_previous_signals()
    new_signals = {}
    new_alerts = []

    for symbol in crypto_symbols:
        try:
            df = fetch_crypto_data(symbol)
            analyze_asset(symbol, df, is_crypto=True, prev_signals=prev_signals,
                          new_signals=new_signals, new_alerts=new_alerts)
        except Exception as e:
            logging.error(f"Error fetching crypto {symbol}: {e}")

    for ticker in stock_symbols:
        try:
            df = fetch_stock_data(ticker)
            analyze_asset(ticker, df, is_crypto=False, prev_signals=prev_signals,
                          new_signals=new_signals, new_alerts=new_alerts)
        except Exception as e:
            logging.error(f"Error fetching stock {ticker}: {e}")

    if new_alerts:
        message = "\n\n".join(new_alerts)
        subject = f"📈 Market Signal Updates ({len(new_alerts)} changes)"
        send_email(subject, message.replace("\n", "<br>"))
        send_telegram(message)

    save_signals(new_signals)
