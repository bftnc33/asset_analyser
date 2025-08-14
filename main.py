import os
import json
import logging
import ta
from alerts import send_email, send_telegram
from data_feeds import fetch_crypto_data, fetch_stock_data

# --- Setup Logging ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# --- CONFIG ---
SIGNAL_FILE = "signals.json"
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

# --- INDICATORS ---
def add_indicators(df):
    df['sma7'] = ta.trend.sma_indicator(df['close'], window=7)
    df['sma30'] = ta.trend.sma_indicator(df['close'], window=30)
    df['sma200'] = ta.trend.sma_indicator(df['close'], window=200)  # Add SMA200
    df['rsi'] = ta.momentum.rsi(df['close'], window=14)
    df['vol_avg'] = df['volume'].ewm(span=20, adjust=False).mean()
    
    # Add MACD
    macd = ta.trend.MACD(df['close'])
    df['macd'] = macd.macd()
    df['macd_signal'] = macd.macd_signal()
    df['macd_histogram'] = macd.macd_diff()
    
    return df

# --- VOLUME COLOR DETECTION ---
def get_volume_color(df, latest_idx):
    """Determine if volume candle is green (buying) or red (selling)"""
    if latest_idx < 1:
        return "neutral"
    
    current = df.iloc[latest_idx]
    previous = df.iloc[latest_idx - 1]
    
    # Green volume = price up from previous close
    # Red volume = price down from previous close
    if current.close > previous.close:
        return "green"
    elif current.close < previous.close:
        return "red"
    else:
        return "neutral"

# --- SMART MONEY CONTEXT ---
def get_smart_money_context(latest, volume_color, spike_ratio, rsi_value, sma200_distance):
    """Enhanced smart money interpretation including SMA200 context"""
    price_change_pct = ((latest.close - latest.open) / latest.open) * 100
    
    # Enhanced logic with SMA200 context
    if volume_color == "red" and abs(price_change_pct) < 0.5 and spike_ratio > 1.5:
        if sma200_distance > 10:
            return "🔍 Smart Money: Distribution (Extended above 200MA)"
        else:
            return "🔍 Smart Money: Distribution (Heavy selling, minimal price impact)"
    elif volume_color == "green" and abs(price_change_pct) < 0.5 and spike_ratio > 1.5:
        if sma200_distance < -10:
            return "🔍 Smart Money: Accumulation (Oversold vs 200MA)"
        else:
            return "🔍 Smart Money: Accumulation (Heavy buying, controlled price)"
    elif volume_color == "red" and price_change_pct < -2 and rsi_value < 40:
        if abs(sma200_distance) < 5:
            return "🔍 Smart Money: 200MA support test"
        else:
            return "🔍 Smart Money: Capitulation absorbed"
    elif volume_color == "green" and price_change_pct > 2 and rsi_value > 60:
        if sma200_distance > 15:
            return "🔍 Smart Money: FOMO buying (Extended from 200MA)"
        else:
            return "🔍 Smart Money: FOMO buying (Caution)"
    
    return ""

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

# --- MACD SIGNAL DETECTION ---
def get_macd_signal(df, latest_idx):
    if latest_idx < 2:  # Need at least 3 data points
        return ""
    
    current = df.iloc[latest_idx]
    previous = df.iloc[latest_idx - 1]
    two_days_ago = df.iloc[latest_idx - 2]
    
    # Current MACD relationship
    macd_above_signal = current.macd > current.macd_signal
    
    # Crossover detection (existing logic)
    bullish_crossover = (previous.macd <= previous.macd_signal and current.macd > current.macd_signal)
    bearish_crossover = (previous.macd >= previous.macd_signal and current.macd < current.macd_signal)
    
    # NEW: Momentum change detection
    macd_momentum_change = current.macd - previous.macd
    prev_momentum_change = previous.macd - two_days_ago.macd
    momentum_acceleration = macd_momentum_change - prev_momentum_change
    
    # NEW: Histogram momentum (more sensitive)
    histogram_change = current.macd_histogram - previous.macd_histogram
    prev_histogram_change = previous.macd_histogram - two_days_ago.macd_histogram
    
    # Priority 1: Actual crossovers (existing logic)
    if bullish_crossover:
        return "🚀 MACD Bullish Cross"
    elif bearish_crossover:
        return "⚠️ MACD Bearish Cross"
    
    # Priority 2: Strong momentum signals (existing logic)
    elif macd_above_signal and current.macd_histogram > 0:
        if current.macd_histogram > previous.macd_histogram * 1.5:
            return "🔥 MACD Strong Bull"
    elif not macd_above_signal and current.macd_histogram < 0:
        if current.macd_histogram < previous.macd_histogram * 1.5:
            return "🔻 MACD Strong Bear"
    
    # Priority 3: NEW - Momentum building (no crossover yet)
    elif macd_above_signal:  # MACD above signal line
        # Bullish momentum building
        if histogram_change > 0 and abs(histogram_change) > abs(prev_histogram_change) * 1.2:
            return "📈 MACD Momentum+"
        # Bullish momentum weakening
        elif histogram_change < 0 and abs(histogram_change) > abs(prev_histogram_change) * 1.2:
            return "📉 MACD Momentum-"
    
    elif not macd_above_signal:  # MACD below signal line
        # Bearish momentum building (getting more negative)
        if histogram_change < 0 and abs(histogram_change) > abs(prev_histogram_change) * 1.2:
            return "📉 MACD Momentum-"
        # Bearish momentum weakening (getting less negative)
        elif histogram_change > 0 and abs(histogram_change) > abs(prev_histogram_change) * 1.2:
            return "📈 MACD Momentum+"
    
    # Priority 4: NEW - Subtle trend changes
    if abs(momentum_acceleration) > 0.01:  # Adjust threshold as needed
        if macd_above_signal:
            if momentum_acceleration > 0:
                return "⬆️ MACD Accelerating"
            else:
                return "⬇️ MACD Decelerating"
        else:
            if momentum_acceleration < 0:
                return "⬇️ MACD Accelerating"  # More bearish = accelerating downward
            else:
                return "⬆️ MACD Decelerating"  # Less bearish = decelerating downward
    
    return ""

# --- SIGNAL GENERATION ---
def generate_signal(df, latest, prev, rsi_desc):
    sma7, sma30, sma200 = latest.sma7, latest.sma30, latest.sma200
    prev_sma7, prev_sma30, prev_sma200 = prev.sma7, prev.sma30, prev.sma200

    # Enhanced flag logic with SMA200 context
    if sma7 > sma30:
        if latest.close > sma200:
            flag = "📈 Bull Flag (Above 200MA)"
        else:
            flag = "📈 Bull Flag (Below 200MA - Counter-trend)"
    else:
        if latest.close > sma200:
            flag = "📉 Bear Flag (Above 200MA - Counter-trend)"
        else:
            flag = "📉 Bear Flag (Below 200MA)"

    trend = "🔼 Daily UP" if latest.close > prev.close else "🔽 Daily DOWN"
    price_vs_sma7 = "✅ Price ABOVE SMA7" if latest.close > sma7 else "🔻 Price BELOW SMA7" 
    price_vs_sma30 = "✅ Price ABOVE SMA30" if latest.close > sma30 else "🔻 Price BELOW SMA30"
    price_vs_sma200 = "✅ Price ABOVE SMA200" if latest.close > sma200 else "🔻 Price BELOW SMA200"

    # Enhanced crossover detection including SMA200
    crossover = ""
    if prev_sma7 < prev_sma30 and sma7 > sma30:
        crossover = "✨ Golden Cross (SMA7 ↑ SMA30)"
    elif prev_sma7 > prev_sma30 and sma7 < sma30:
        crossover = "⚠️ Death Cross (SMA7 ↓ SMA30)"
    
    # NEW: SMA200 crossovers (major institutional signals)
    sma200_cross = ""
    if prev.close <= prev_sma200 and latest.close > sma200:
        sma200_cross = "🚀 MAJOR: Price crossed ABOVE 200MA"
    elif prev.close >= prev_sma200 and latest.close < sma200:
        sma200_cross = "💥 MAJOR: Price crossed BELOW 200MA"

    # Distance from SMA200 (smart money context)
    sma200_distance = ((latest.close - sma200) / sma200) * 100
    sma200_context = ""
    if abs(sma200_distance) > 20:
        if sma200_distance > 0:
            sma200_context = f"📈 Extended above 200MA (+{sma200_distance:.1f}%)"
        else:
            sma200_context = f"📉 Extended below 200MA ({sma200_distance:.1f}%)"
    elif abs(sma200_distance) < 2:
        sma200_context = "⚡ Near 200MA (Decision zone)"

    # Get MACD signal
    macd_signal = get_macd_signal(df, len(df) - 1)

    # Enhanced Volume Analysis with Color
    spike_ratio = latest.volume / latest.vol_avg if latest.vol_avg else 0
    volume_color = get_volume_color(df, len(df) - 1)
    
    volume_spike = ""
    if spike_ratio > 2:
        if volume_color == "green":
            volume_spike = "📊🟢 Volume Spike: 🚨 BUYING SURGE"
        elif volume_color == "red":
            volume_spike = "📊🔴 Volume Spike: 🚨 SELLING PRESSURE"
        else:
            volume_spike = "📊⚪️ Volume Spike: 🚨 Severe (Neutral)"
    elif spike_ratio > 1.5:
        if volume_color == "green":
            volume_spike = "📊🟢 Volume Spike: ⚠️ BUYING Interest"
        elif volume_color == "red":
            volume_spike = "📊🔴 Volume Spike: ⚠️ SELLING Pressure"
        else:
            volume_spike = "📊⚪️ Volume Spike: ⚠️ Moderate"
    elif spike_ratio > 1.2:
        if volume_color == "green":
            volume_spike = "📊🟢 Volume↑ (Buying)"
        elif volume_color == "red":
            volume_spike = "📊🔴 Volume↑ (Selling)"
        else:
            volume_spike = "📊⚪️ Volume↑"

    # Enhanced smart money context with SMA200
    smart_money_context = get_smart_money_context(latest, volume_color, spike_ratio, latest.rsi, sma200_distance)

    rsi_change = latest.rsi - prev.rsi
    rsi_momentum = ""
    if abs(rsi_change) > 5:
        direction = "↗️ Accelerating" if rsi_change > 0 else "↘️ Decelerating"
        rsi_momentum = f"RSI {direction}"

    # Build signal parts
    parts = [flag, trend, price_vs_sma7, price_vs_sma30, price_vs_sma200]
    if crossover:
        parts.append(crossover)
    if sma200_cross:  # Major SMA200 crossover
        parts.append(sma200_cross)
    if macd_signal:
        parts.append(macd_signal)
    if volume_spike:
        parts.append(volume_spike)
    parts.append(rsi_desc)
    if rsi_momentum:
        parts.append(rsi_momentum)
    if sma200_context:
        parts.append(sma200_context)
    if smart_money_context:
        parts.append(smart_money_context)

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

    removed = old_items - new_items_set

    # Build signal with (was: old_value) for changed items
    enhanced_signal_parts = []
    
    for new_item in new_items_list:
        enhanced_part = new_item
        
        # Check if this new item replaces an old one (same category)
        for old_item in removed:
            # Check for similar categories that should show "was:" format
            if (('Bull Flag' in new_item or 'Bear Flag' in new_item) and ('Bull Flag' in old_item or 'Bear Flag' in old_item)) or \
               (('Daily UP' in new_item or 'Daily DOWN' in new_item) and ('Daily UP' in old_item or 'Daily DOWN' in old_item)) or \
               (('ABOVE SMA7' in new_item or 'BELOW SMA7' in new_item) and ('ABOVE SMA7' in old_item or 'BELOW SMA7' in old_item)) or \
               (('ABOVE SMA30' in new_item or 'BELOW SMA30' in new_item) and ('ABOVE SMA30' in old_item or 'BELOW SMA30' in old_item)) or \
               (('RSI' in new_item and 'RSI' in old_item)) or \
               (('MACD' in new_item and 'MACD' in old_item)):  # Added MACD change detection
                enhanced_part = f"{new_item} (was: {old_item})"
                break
        
        enhanced_signal_parts.append(enhanced_part)
    
    return " | ".join(enhanced_signal_parts)

# --- ENHANCED FORMAT OUTPUT ---
def format_output(symbol, latest, previous, signal, rsi_desc, is_crypto, changes=None):
    # Determine currency and formatting
    if symbol.endswith("SGLN.L"):
        currency = "£"
        suffix = ""
        # Convert pence to pounds by dividing by 100
        current_close = latest.close / 100
        previous_close = previous.close / 100
        price_fmt = "{:,.4f}" if current_close < 1 else "{:,.2f}"
    elif symbol.endswith(".L"):
        currency = "£"
        suffix = ""
        price_fmt = "{:,.4f}" if latest.close < 1 else "{:,.2f}"
        current_close = latest.close
        previous_close = previous.close
    elif is_crypto:
        # Crypto in GBP
        currency = "£"
        suffix = ""
        price_fmt = "{:,.4f}" if latest.close < 1 else "{:,.2f}"
        current_close = latest.close
        previous_close = previous.close
    else:
        # US stocks in USD
        currency = "$"
        suffix = ""
        price_fmt = "{:,.4f}" if latest.close < 1 else "{:,.2f}"
        current_close = latest.close
        previous_close = previous.close
    
    price_change = ((current_close - previous_close) / previous_close) * 100
    change_color = "🟢" if price_change > 0 else "🔴" if price_change < 0 else "⚪️"
    
    # Parse the signal to build current status
    signal_parts = signal.split(' | ')
    
    # Extract only the current status (before any "was:" text)
    def extract_current_status(part):
        """Extract the current status from a signal part, ignoring (was: ...) sections"""
        if "(was:" in part:
            return part.split("(was:")[0].strip()
        return part.strip()
    
    # Build compact status line using only current status
    current_parts = [extract_current_status(part) for part in signal_parts]
    
    flag = "📈 Bull" if any("Bull Flag" in part for part in current_parts) else "📉 Bear"
    above_sma7 = "✅" if any("Price ABOVE SMA7" in part for part in current_parts) else "🔻"
    above_sma30 = "✅" if any("Price ABOVE SMA30" in part for part in current_parts) else "🔻"
    above_sma200 = "✅" if any("Price ABOVE SMA200" in part for part in current_parts) else "🔻"
    
    # Add MACD status
    macd_status = ""
    
    # Priority order for MACD display
    if any("MACD Bullish Cross" in part for part in current_parts):
        macd_status = "🚀"
    elif any("MACD Bearish Cross" in part for part in current_parts):
        macd_status = "⚠️"
    elif any("MACD Strong Bull" in part for part in current_parts):
        macd_status = "🔥"
    elif any("MACD Strong Bear" in part for part in current_parts):
        macd_status = "🔻"
    elif any("MACD Momentum+" in part for part in current_parts):
        macd_status = "📈"
    elif any("MACD Momentum-" in part for part in current_parts):
        macd_status = "📉"
    elif any("MACD Accelerating" in part for part in current_parts):
        macd_status = "⬆️"
    elif any("MACD Decelerating" in part for part in current_parts):
        macd_status = "⬇️"
    else:
        # Fallback to basic above/below signal line
        if hasattr(latest, 'macd') and hasattr(latest, 'macd_signal'):
            if latest.macd > latest.macd_signal:
                macd_status = "✅"
            else:
                macd_status = "🔻"
    
    # RSI with momentum arrow if accelerating
    rsi_arrow = ""
    if any("RSI ↗️ Accelerating" in part for part in current_parts):
        rsi_arrow = "↗️"
    elif any("RSI ↘️ Decelerating" in part for part in current_parts):
        rsi_arrow = "↘️"
    
    rsi_status = f"RSI:{latest.rsi:.0f}{rsi_arrow}"
    
    # Build main status line
    status_parts = [flag, f"{above_sma7}SMA7", f"{above_sma30}SMA30", f"{above_sma200}SMA200"]
    if macd_status:
        status_parts.append(f"{macd_status}MACD")
    status_parts.append(rsi_status)
    
    main_line = f"{symbol}: {currency}{price_fmt.format(current_close)}{suffix} {change_color}{price_change:+.1f}% | {' | '.join(status_parts)}"
    
    # Extract key changes for second line
    key_changes = []
    
    for part in signal_parts:
        part = part.strip()
        if "(was:" in part:
            # Extract the change
            if "ABOVE SMA7" in part and "was: 🔻 Price BELOW SMA7" in part:
                key_changes.append("✅ Broke ABOVE SMA7")
            elif "BELOW SMA7" in part and "was: ✅ Price ABOVE SMA7" in part:
                key_changes.append("🔻 Broke BELOW SMA7")
            elif "ABOVE SMA30" in part and "was: 🔻 Price BELOW SMA30" in part:
                key_changes.append("✅ Broke ABOVE SMA30")
            elif "BELOW SMA30" in part and "was: ✅ Price ABOVE SMA30" in part:
                key_changes.append("🔻 Broke BELOW SMA30")
            elif "Bull Flag" in part and "was: 📉 Bear Flag" in part:
                key_changes.append("📈 Turned BULLISH")
            elif "Bear Flag" in part and "was: 📈 Bull Flag" in part:
                key_changes.append("📉 Turned BEARISH")
            elif "Daily UP" in part and "was: 🔽 Daily DOWN" in part:
                key_changes.append("🔼 Daily UP")
            elif "Daily DOWN" in part and "was: 🔼 Daily UP" in part:
                key_changes.append("🔽 Daily DOWN")
            elif "Golden Cross" in part:
                key_changes.append("✨ Golden Cross")
            elif "Death Cross" in part:
                key_changes.append("⚠️ Death Cross")
            elif "MACD Bullish Cross" in part:
                key_changes.append("🚀 MACD Bull Cross")
            elif "MACD Bearish Cross" in part:
                key_changes.append("⚠️ MACD Bear Cross")
            elif "RSI" in part:
                # Handle RSI changes
                if "OVERSOLD" in part:
                    key_changes.append(f"🟢 RSI OVERSOLD ({latest.rsi:.0f})")
                elif "OVERBOUGHT" in part:
                    key_changes.append(f"🔴 RSI OVERBOUGHT ({latest.rsi:.0f})")
                elif "Near Overbought" in part:
                    key_changes.append(f"🟡 RSI heating up ({latest.rsi:.0f}→overbought)")
                elif "Near Oversold" in part:
                    key_changes.append(f"🟡 RSI cooling ({latest.rsi:.0f}→oversold)")
                elif "Neutral" in part and "was:" in part:
                    if latest.rsi > 55:
                        key_changes.append(f"⚪️ RSI normalizing ({latest.rsi:.0f})")
    
    # Enhanced MACD change detection
    for part in current_parts:
        if "🚀 MACD Bullish Cross" in part and not any("MACD" in change for change in key_changes):
            key_changes.append("🚀 MACD Bull Cross")
        elif "⚠️ MACD Bearish Cross" in part and not any("MACD" in change for change in key_changes):
            key_changes.append("⚠️ MACD Bear Cross")
        elif "🔥 MACD Strong Bull" in part:
            key_changes.append("🔥 MACD Strong Bull")
        elif "🔻 MACD Strong Bear" in part:
            key_changes.append("🔻 MACD Strong Bear")
        elif "📈 MACD Momentum+" in part:
            key_changes.append("📈 MACD Building")
        elif "📉 MACD Momentum-" in part:
            key_changes.append("📉 MACD Weakening")
        elif "⬆️ MACD Accelerating" in part:
            key_changes.append("⬆️ MACD Accelerating")
        elif "⬇️ MACD Decelerating" in part:
            key_changes.append("⬇️ MACD Decelerating")
    
    # Add RSI momentum if present (and not already in arrow)
    for part in current_parts:
        # Skip if we already have an RSI change message
        if any("RSI" in change for change in key_changes):
            continue

        if "RSI ↗️ Accelerating" in part:
            if not any("RSI" in change for change in key_changes) and not rsi_arrow:
                key_changes.append(f"📈 RSI accelerating ({latest.rsi:.0f}↗️)")
        elif "RSI ↘️ Decelerating" in part:
            if not any("RSI" in change for change in key_changes) and not rsi_arrow:
                key_changes.append(f"📉 RSI decelerating ({latest.rsi:.0f}↘️)")
    
    # Enhanced volume spikes with color
    for part in current_parts:
        if "🟢" in part and "BUYING SURGE" in part:
            key_changes.append("🟢📊 BUYING SURGE")
        elif "🔴" in part and "SELLING PRESSURE" in part:
            key_changes.append("🔴📊 SELLING PRESSURE") 
        elif "🟢" in part and "BUYING Interest" in part:
            key_changes.append("🟢📊 Buying Interest")
        elif "🔴" in part and "SELLING Pressure" in part:
            key_changes.append("🔴📊 Selling Pressure")
        elif "🟢" in part and "Volume↑ (Buying)" in part:
            key_changes.append("🟢📊 Volume↑")
        elif "🔴" in part and "Volume↑ (Selling)" in part:
            key_changes.append("🔴📊 Volume↑")
        elif "Volume Spike: 🚨 Severe" in part:  # Keep existing neutral logic
            key_changes.append("📊 VOLUME SURGE")
        elif "Smart Money: Distribution" in part:
            key_changes.append("🔍 Distribution")
        elif "Smart Money: Accumulation" in part:
            key_changes.append("🔍 Accumulation")
        elif "Smart Money: Capitulation absorbed" in part:
            key_changes.append("🔍 Capitulation absorbed")
        elif "Smart Money: FOMO buying" in part:
            key_changes.append("🔍 FOMO buying")
    
    # Return format: always show status line, add changes if any
    if key_changes:
        changes_line = f"   {' | '.join(key_changes)}"
        return f"{main_line}\n{changes_line}"
    else:
        return main_line

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