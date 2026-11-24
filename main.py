import os
import json
import logging
from alerts import send_email
from data_feeds import fetch_crypto_data, fetch_stock_data
from technical_analysis import analyse_asset

# --- Setup Logging ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

# --- CONFIG ---
SIGNAL_FILE = "signals.json"

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

def build_email_html(alerts):
    """Wrap coloured asset rows in a dark-background email shell."""
    rows = "\n".join(alerts)
    return f"""
<html>
<body style="background-color:#1a1a1a; padding:16px; margin:0;">
  <div style="max-width:900px; margin:0 auto;">
    <h2 style="color:#e0e0e0; font-family:sans-serif; margin-bottom:12px;">
      📈 Weekly Market Summary
    </h2>
    {rows}
  </div>
</body>
</html>
"""

# --- MAIN LOOP ---
if __name__ == "__main__":
    prev_signals = load_previous_signals()
    new_signals = {}
    new_alerts = []

    # Process crypto assets
    logging.info(
        f"📊 Analyzing {len(crypto_symbols)} crypto assets "
        f"(weekly timeframe)..."
    )
    for symbol in crypto_symbols:
        try:
            df = fetch_crypto_data(symbol)
            analyse_asset(symbol, df, is_crypto=True,
                          prev_signals=prev_signals,
                          new_signals=new_signals,
                          new_alerts=new_alerts)
        except Exception as e:
            logging.error(f"Error fetching crypto {symbol}: {e}")

    # Process stock assets
    logging.info(
        f"📊 Analyzing {len(stock_symbols)} stock assets "
        f"(weekly timeframe)..."
    )
    for ticker in stock_symbols:
        try:
            df = fetch_stock_data(ticker)
            analyse_asset(ticker, df, is_crypto=False,
                          prev_signals=prev_signals,
                          new_signals=new_signals,
                          new_alerts=new_alerts)
        except Exception as e:
            logging.error(f"Error fetching stock {ticker}: {e}")

    # Send weekly summary email
    if new_alerts:
        subject = f"📈 Weekly Market Summary ({len(new_alerts)} assets)"
        send_email(subject, build_email_html(new_alerts))
        logging.info(
            f"✅ Sent weekly summary email with {len(new_alerts)} assets"
        )
    else:
        logging.info("ℹ️ No assets to report this week")

    # Save current signals for next run
    save_signals(new_signals)
    logging.info(f"💾 Saved {len(new_signals)} signals to {SIGNAL_FILE}")