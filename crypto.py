import ccxt
import pandas as pd
import ta
from dotenv import load_dotenv
import os
import smtplib
from email.message import EmailMessage

# --- LOAD ENVIRONMENT VARIABLES ---
load_dotenv()

EMAIL_ADDRESS = os.getenv('EMAIL_ADDRESS')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')
SMTP_SERVER = os.getenv('SMTP_SERVER')
SMTP_PORT = int(os.getenv('SMTP_PORT', 587))

# --- CONFIG ---
symbols = ['BTC/GBP','ETH/GBP','XRP/GBP','SOL/GBP','ADA/GBP','XLM/GBP','SAND/GBP']
timeframe = '1d'
limit = 100
exchange = ccxt.kraken()

# --- EMAIL FUNCTION ---
def send_email(subject, body):
    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = EMAIL_ADDRESS
    msg['To'] = EMAIL_ADDRESS  # You can add multiple recipients separated by commas
    msg.set_content(body)

    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as smtp:
        smtp.starttls()
        smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        smtp.send_message(msg)

# --- FETCH DATA ---
def fetch_data(symbol):
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    df = pd.DataFrame(ohlcv, columns=['timestamp','open','high','low','close','volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
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

    # fallback to trend-based logic
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

# --- MAIN LOOP ---
if __name__ == "__main__":
    for symbol in symbols:
        df = fetch_data(symbol)
        df = add_indicators(df)
        df.dropna(inplace=True)
        if len(df) < 2:
            print(f"{symbol}: Not enough data.")
            continue

        signal = generate_signal(df)
        price = df.iloc[-1]['close']
        sma7 = df.iloc[-1]['sma7']
        sma30 = df.iloc[-1]['sma30']
        rsi = df.iloc[-1]['rsi']

        output = (f"\n🔹 {symbol}:\n"
                  f"   Price: £{price:,.2f}\n"
                  f"   SMA7: £{sma7:,.2f} | SMA30: £{sma30:,.2f} | RSI: {rsi:.2f}\n"
                  f"   Signal: {signal}")

        print(output)

        if 'STRONG BUY' in signal or 'STRONG SELL' in signal:
            subject = f"{symbol} Alert: {signal}"
            send_email(subject, output)
