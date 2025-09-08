import os
import json
import logging
from alerts import send_email
from data_feeds import fetch_crypto_data, fetch_stock_data
from technical_analysis import analyse_asset, generate_html_table

# --- Setup Logging ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# --- CONFIG ---
SIGNAL_FILE = "signals.json"
HTML_FILE = "weekly_analysis.html"
timeframe = '1d'
limit = 300

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

def save_html_report(html_content):
    """Save HTML report to file"""
    try:
        with open(HTML_FILE, "w", encoding='utf-8') as f:
            f.write(html_content)
        logging.info(f"HTML report saved to {HTML_FILE}")
    except Exception as e:
        logging.error(f"Error saving HTML report: {e}")

def send_html_email(html_content, has_alerts, alert_count):
    """Send email with HTML table and alert summary"""
    try:
        if has_alerts:
            subject = f"📈 Weekly Trading Analysis - {alert_count} Alert(s)"
        else:
            subject = "📊 Weekly Trading Analysis - No Changes"
        
        # Send the HTML table as the email body
        send_email(subject, html_content)
        logging.info("HTML email sent successfully")
        
    except Exception as e:
        logging.error(f"Error sending HTML email: {e}")

# --- MAIN LOOP ---
if __name__ == "__main__":
    prev_signals = load_previous_signals()
    new_signals = {}
    new_alerts = []
    html_results = []
    
    logging.info("Starting weekly analysis...")
    
    # Process crypto symbols
    logging.info(f"Processing {len(crypto_symbols)} crypto symbols...")
    for symbol in crypto_symbols:
        try:
            df = fetch_crypto_data(symbol)
            if df is not None and not df.empty:
                analyse_asset(symbol, df, is_crypto=True, prev_signals=prev_signals,
                             new_signals=new_signals, new_alerts=new_alerts, html_results=html_results)
        except Exception as e:
            logging.error(f"Error processing crypto {symbol}: {e}")
    
    # Process stock symbols
    logging.info(f"Processing {len(stock_symbols)} stock symbols...")
    for ticker in stock_symbols:
        try:
            df = fetch_stock_data(ticker)
            if df is not None and not df.empty:
                analyse_asset(ticker, df, is_crypto=False, prev_signals=prev_signals,
                             new_signals=new_signals, new_alerts=new_alerts, html_results=html_results)
        except Exception as e:
            logging.error(f"Error processing stock {ticker}: {e}")
    
    # Generate HTML table and send email
    if html_results:
        logging.info(f"Generating HTML report for {len(html_results)} assets...")
        html_content = generate_html_table(html_results)
        
        # Save HTML report to file
        save_html_report(html_content)
        
        # Count alerts (assets with notes)
        alert_count = sum(1 for result in html_results if result['notes'])
        has_alerts = alert_count > 0
        
        if has_alerts:
            logging.info(f"Found {alert_count} alert(s)")
        else:
            logging.info("No alerts found")
        
        # Send HTML email
        send_html_email(html_content, has_alerts, alert_count)
        
        # Save signals for next run
        save_signals(new_signals)
        
        logging.info(f"Analysis complete: {len(html_results)} assets processed, {alert_count} alerts")
        
    else:
        logging.warning("No data processed - check your data feeds and symbol configuration")
        
    logging.info("Weekly analysis finished")