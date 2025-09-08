import logging
import ta
import pandas as pd

# --- Setup Logging ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

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
               (('Weekly UP' in new_item or 'Weekly DOWN' in new_item) and ('Weekly UP' in old_item or 'Weekly DOWN' in old_item)) or \
               (('ABOVE SMA8' in new_item or 'BELOW SMA8' in new_item) and ('ABOVE SMA8' in old_item or 'BELOW SMA8' in old_item)) or \
               (('ABOVE SMA21' in new_item or 'BELOW SMA21' in new_item) and ('ABOVE SMA21' in old_item or 'BELOW SMA21' in old_item)) or \
               (('ABOVE SMA55' in new_item or 'BELOW SMA55' in new_item) and ('ABOVE SMA55' in old_item or 'BELOW SMA55' in old_item)) or \
               (('MACD' in new_item and 'MACD' in old_item)):
                enhanced_part = f"{new_item} (was: {old_item})"
                break
        enhanced_signal_parts.append(enhanced_part)

    return " | ".join(enhanced_signal_parts)

# --- FORMAT OUTPUT ---
def format_output(symbol, latest, previous, signal, rsi_desc, is_crypto, changes=None):
    """Return structured data for HTML table instead of formatted string"""
    
    # Determine currency and formatting (same logic as original)
    if symbol.endswith("SGLN.L"):
        currency = "£"
        current_close = latest.close / 100
        previous_close = previous.close / 100
        price_fmt = "{:,.4f}" if current_close < 1 else "{:,.2f}"
    elif symbol.endswith(".L"):
        currency = "£"
        price_fmt = "{:,.4f}" if latest.close < 1 else "{:,.2f}"
        current_close = latest.close
        previous_close = previous.close
    elif is_crypto:
        currency = "£"
        price_fmt = "{:,.4f}" if latest.close < 1 else "{:,.2f}"
        current_close = latest.close
        previous_close = previous.close
    else:
        currency = "$"
        price_fmt = "{:,.4f}" if latest.close < 1 else "{:,.2f}"
        current_close = latest.close
        previous_close = previous.close
    
    price_change = ((current_close - previous_close) / previous_close) * 100
    change_color = "🟢" if price_change > 0 else "🔴" if price_change < 0 else "⚪️"
    
    # Parse signal parts
    signal_parts = signal.split(' | ')
    
    def extract_current_status(part):
        if "(was:" in part:
            return part.split("(was:")[0].strip()
        return part.strip()
    
    current_parts = [extract_current_status(part) for part in signal_parts]
    
    # Extract individual components
    flag = "📈" if any("Bull Flag" in part for part in current_parts) else "📉"
    flag_text = "Bull" if flag == "📈" else "Bear"
    
    # SMA status
    sma8_status = "✅" if any(part == "✅ Price ABOVE SMA8" for part in current_parts) else "🔻"
    sma21_status = "✅" if any(part == "✅ Price ABOVE SMA21" for part in current_parts) else "🔻"
    sma55_status = "✅" if any(part == "✅ Price ABOVE SMA55" for part in current_parts) else "🔻"
    
    # SMA144 and SMA233 status
    sma144_status = ""
    if any("ABOVE SMA144" in part or "BELOW SMA144" in part for part in current_parts):
        sma144_status = "✅" if any(part == "✅ Price ABOVE SMA144" for part in current_parts) else "🔻"
    
    sma233_status = ""
    if any("ABOVE SMA233" in part or "BELOW SMA233" in part for part in current_parts):
        sma233_status = "✅" if any(part == "✅ Price ABOVE SMA233" for part in current_parts) else "🔻"
    
    # MACD status
    macd_status = ""
    macd_emoji = ""
    for part in current_parts:
        if "🚀 MACD Bullish Cross" in part:
            macd_emoji = "🚀"
            macd_status = "Bull Cross"
            break
        elif "⚠️ MACD Bearish Cross" in part:
            macd_emoji = "⚠️"
            macd_status = "Bear Cross"
            break
        elif "🔥 MACD Strong Bull" in part:
            macd_emoji = "🔥"
            macd_status = "Strong Bull"
            break
        elif "🔻 MACD Strong Bear" in part:
            macd_emoji = "🔻"
            macd_status = "Strong Bear"
            break
        elif "✅⬆️ MACD" in part:
            macd_emoji = "✅⬆️"
            macd_status = "Bullish"
            break
        elif "✅⬇️ MACD" in part:
            macd_emoji = "✅⬇️"
            macd_status = "Bull Weak"
            break
        elif "🔻⬆️ MACD" in part:
            macd_emoji = "🔻⬆️"
            macd_status = "Bear Weak"
            break
        elif "🔻⬇️ MACD" in part:
            macd_emoji = "🔻⬇️"
            macd_status = "Bearish"
            break
    
    # RSI
    rsi_value = latest.rsi
    
    # Get SMA period for display
    actual_sma_period = latest.sma_period if hasattr(latest, 'sma_period') else 55
    
    # Extract notes/changes from signal
    notes = []
    for part in signal_parts:
        part = part.strip()
        if "(was:" in part:
            if "ABOVE SMA8" in part and "was: 🔻 Price BELOW SMA8" in part:
                notes.append("✅ Broke ABOVE SMA8")
            elif "BELOW SMA8" in part and "was: ✅ Price ABOVE SMA8" in part:
                notes.append("🔻 Broke BELOW SMA8")
            elif "ABOVE SMA21" in part and "was: 🔻 Price BELOW SMA21" in part:
                notes.append("✅ Broke ABOVE SMA21")
            elif "BELOW SMA21" in part and "was: ✅ Price ABOVE SMA21" in part:
                notes.append("🔻 Broke BELOW SMA21")
            elif f"ABOVE SMA{actual_sma_period}" in part and f"was: 🔻 Price BELOW SMA{actual_sma_period}" in part:
                notes.append(f"✅ Broke ABOVE SMA{actual_sma_period}")
            elif "Bull Flag" in part and "was: 📉 Bear Flag" in part:
                notes.append("📈 Turned BULLISH")
            elif "Bear Flag" in part and "was: 📈 Bull Flag" in part:
                notes.append("📉 Turned BEARISH")
            elif "Weekly UP" in part and "was: 🔽 Weekly DOWN" in part:
                notes.append("🔼 Weekly UP")
            elif "Weekly DOWN" in part and "was: 🔼 Weekly UP" in part:
                notes.append("🔽 Weekly DOWN")
            elif "MACD Bullish Cross" in part:
                notes.append("🚀 MACD Bull Cross")
            elif "MACD Bearish Cross" in part:
                notes.append("⚠️ MACD Bear Cross")
    
    # Add RSI conditions
    if "🟢 RSI OVERSOLD" in rsi_desc:
        notes.append(f"🟢 RSI OVERSOLD ({rsi_value:.0f})")
    elif "🔴 RSI OVERBOUGHT" in rsi_desc:
        notes.append(f"🔴 RSI OVERBOUGHT ({rsi_value:.0f})")
    elif "🟡 RSI Near Overbought" in rsi_desc:
        notes.append(f"🟡 RSI heating up ({rsi_value:.0f}→overbought)")
    elif "🟡 RSI Near Oversold" in rsi_desc:
        notes.append(f"🟡 RSI cooling ({rsi_value:.0f}→oversold)")
    
    return {
        'symbol': symbol,
        'price': f"{currency}{price_fmt.format(current_close)}",
        'change': f"{change_color}{price_change:+.1f}%",
        'flag': flag,
        'flag_text': flag_text,
        'sma8': sma8_status,
        'sma21': sma21_status,
        'sma55': sma55_status,
        'sma55_period': actual_sma_period,
        'sma144': sma144_status,
        'sma233': sma233_status,
        'macd_emoji': macd_emoji,
        'macd_status': macd_status,
        'rsi': f"{rsi_value:.0f}",
        'notes': ' | '.join(notes) if notes else ''
    }

def generate_html_table(analysis_results):
    """Generate HTML table from analysis results"""
    
    html = '''
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Weekly Trading Analysis</title>
        <style>
            body {
                font-family: 'Segoe UI', Arial, sans-serif;
                margin: 20px;
                background-color: #f5f5f5;
            }
            .container {
                max-width: 1400px;
                margin: 0 auto;
                background-color: white;
                padding: 20px;
                border-radius: 8px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }
            h1 {
                color: #333;
                text-align: center;
                margin-bottom: 30px;
                border-bottom: 3px solid #4CAF50;
                padding-bottom: 10px;
            }
            table {
                width: 100%;
                border-collapse: collapse;
                margin-bottom: 20px;
                font-size: 14px;
            }
            th {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 12px 8px;
                text-align: center;
                font-weight: 600;
                border: 1px solid #ddd;
                position: sticky;
                top: 0;
                z-index: 10;
            }
            td {
                padding: 10px 8px;
                text-align: center;
                border: 1px solid #ddd;
                vertical-align: middle;
            }
            tr:nth-child(even) {
                background-color: #f8f9fa;
            }
            tr:hover {
                background-color: #e3f2fd;
                transition: background-color 0.2s;
            }
            .symbol {
                font-weight: bold;
                color: #2c3e50;
                text-align: left;
            }
            .price {
                font-weight: bold;
                font-size: 16px;
            }
            .change {
                font-weight: bold;
                font-size: 15px;
            }
            .flag {
                font-size: 18px;
            }
            .sma {
                font-size: 16px;
            }
            .macd {
                font-weight: bold;
            }
            .rsi {
                font-weight: bold;
                color: #34495e;
            }
            .notes {
                text-align: left;
                font-size: 13px;
                color: #555;
                max-width: 200px;
                word-wrap: break-word;
            }
            .timestamp {
                text-align: center;
                color: #666;
                font-style: italic;
                margin-top: 20px;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>📊 Weekly Trading Analysis</h1>
            <table>
                <thead>
                    <tr>
                        <th>Symbol</th>
                        <th>Price</th>
                        <th>Change</th>
                        <th>Flag</th>
                        <th>SMA8</th>
                        <th>SMA21</th>
                        <th>SMA55</th>
                        <th>SMA144</th>
                        <th>SMA233</th>
                        <th>MACD</th>
                        <th>RSI</th>
                        <th>Notes</th>
                    </tr>
                </thead>
                <tbody>
    '''
    
    for result in analysis_results:
        # Handle SMA55 period display
        sma55_header = f"SMA{result['sma55_period']}" if result['sma55_period'] != 55 else "SMA55"
        
        html += f'''
                    <tr>
                        <td class="symbol">{result['symbol']}</td>
                        <td class="price">{result['price']}</td>
                        <td class="change">{result['change']}</td>
                        <td class="flag">{result['flag']}</td>
                        <td class="sma">{result['sma8']}</td>
                        <td class="sma">{result['sma21']}</td>
                        <td class="sma">{result['sma55']}</td>
                        <td class="sma">{result['sma144'] if result['sma144'] else '-'}</td>
                        <td class="sma">{result['sma233'] if result['sma233'] else '-'}</td>
                        <td class="macd">{result['macd_emoji']} {result['macd_status']}</td>
                        <td class="rsi">{result['rsi']}</td>
                        <td class="notes">{result['notes']}</td>
                    </tr>
        '''
    
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    html += f'''
                </tbody>
            </table>
            <div class="timestamp">
                Generated: {timestamp}
            </div>
        </div>
    </body>
    </html>
    '''
    
    return html

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

# --- MACD SIGNAL DETECTION ---
def get_macd_signal(df, latest_idx):
    if latest_idx < 2:
        return ""
    
    try:
        current = df.iloc[latest_idx]
        previous = df.iloc[latest_idx - 1]
        
        # Part 1: MACD Position (positive/negative)
        macd_above_signal = current.macd > current.macd_signal
        
        # Part 2: MACD Momentum (higher/lower than previous)
        macd_momentum_up = current.macd > previous.macd
        
        # Crossover detection (highest priority)
        bullish_crossover = (previous.macd <= previous.macd_signal and current.macd > current.macd_signal)
        bearish_crossover = (previous.macd >= previous.macd_signal and current.macd < current.macd_signal)
        
        # Priority 1: Actual crossovers
        if bullish_crossover:
            return "🚀 MACD Bullish Cross"
        elif bearish_crossover:
            return "⚠️ MACD Bearish Cross"
        
        # Priority 2: Strong momentum signals (weekly timeframe requires bigger moves)
        elif macd_above_signal and current.macd_histogram > 0:
            if current.macd_histogram > previous.macd_histogram * 2.0:  # Higher threshold for weekly
                return "🔥 MACD Strong Bull"
        elif not macd_above_signal and current.macd_histogram < 0:
            if current.macd_histogram < previous.macd_histogram * 2.0:  # Higher threshold for weekly
                return "🔻 MACD Strong Bear"
        
        # Priority 3: Two-part MACD system
        position_indicator = "✅" if macd_above_signal else "🔻"
        momentum_indicator = "⬆️" if macd_momentum_up else "⬇️"
        result = f"{position_indicator}{momentum_indicator} MACD"
        
        return result
    
    except Exception as e:
        print(f"ERROR in get_macd_signal: {e}")
        return ""

# --- SIGNAL GENERATION ---
def generate_signal(df, latest, prev, rsi_desc):
    sma8, sma21, sma55 = latest.sma8, latest.sma21, latest.sma55
    prev_sma8, prev_sma21, prev_sma55 = prev.sma8, prev.sma21, prev.sma55
    
    # Fibonacci-based trend identification system
    if sma8 > sma21 > sma55:
        flag = "📈 Bull Flag (Perfect Fibonacci Alignment)"
    elif sma8 < sma21 < sma55:
        flag = "📉 Bear Flag (Perfect Fibonacci Alignment)"
    else:
        flag = "⚪️ Mixed Signals"
    
    trend = "🔼 Weekly UP" if latest.close > prev.close else "🔽 Weekly DOWN"
    
    price_vs_sma8 = "✅ Price ABOVE SMA8" if latest.close > sma8 else "🔻 Price BELOW SMA8"
    price_vs_sma21 = "✅ Price ABOVE SMA21" if latest.close > sma21 else "🔻 Price BELOW SMA21"
    price_vs_sma55 = "✅ Price ABOVE SMA55" if latest.close > sma55 else "🔻 Price BELOW SMA55"
    
    # Add SMA144 and SMA233 price relationships (only if data exists)
    price_vs_sma144 = ""
    if hasattr(latest, 'sma144') and latest.sma144 is not None and pd.notna(latest.sma144):
        price_vs_sma144 = "✅ Price ABOVE SMA144" if latest.close > latest.sma144 else "🔻 Price BELOW SMA144"
    
    price_vs_sma233 = ""
    if hasattr(latest, 'sma233') and latest.sma233 is not None and pd.notna(latest.sma233):
        price_vs_sma233 = "✅ Price ABOVE SMA233" if latest.close > latest.sma233 else "🔻 Price BELOW SMA233"
    
    # Comprehensive crossover detection system (keeping your existing logic)
    crossover = ""
    if (prev_sma8 <= prev_sma21 or prev_sma21 <= prev_sma55) and \
       (sma8 > sma21 > sma55):
        crossover = "⭐ Perfect Bull Alignment (8>21>55>144>233)"
    elif (prev_sma8 >= prev_sma21 or prev_sma21 >= prev_sma55) and \
         (sma8 < sma21 < sma55):
        crossover = "💀 Perfect Bear Alignment (8<21<55)"
    elif (prev_sma8 <= prev_sma21 and sma8 > sma21) and (sma21 > sma55):
        crossover = "🌟 Major Bull Cross (8↑21, Strong Trend)"
    elif (prev_sma8 >= prev_sma21 and sma8 < sma21) and (sma21 < sma55):
        crossover = "💀 Major Bear Cross (8↓21, Strong Trend)"
    elif prev_sma8 <= prev_sma21 and sma8 > sma21:
        crossover = "✨ Golden Cross (SMA8 ↑ SMA21)"
    elif prev_sma8 >= prev_sma21 and sma8 < sma21:
        crossover = "⚠️ Death Cross (SMA8 ↓ SMA21)"
    elif prev_sma21 <= prev_sma55 and sma21 > sma55:
        crossover = "🚀 Bull Cross (SMA21 ↑ SMA55)"
    elif prev_sma21 >= prev_sma55 and sma21 < sma55:
        crossover = "💥 Bear Cross (SMA21 ↓ SMA55)"
    
    # Price crossover detection for key levels
    price_cross = ""
    if prev.close <= prev_sma55 and latest.close > sma55:
        price_cross = "🚀 Price crossed ABOVE 55MA"
    elif prev.close >= prev_sma55 and latest.close < sma55:
        price_cross = "💥 Price crossed BELOW 55MA"
    
    # Get MACD signal
    macd_signal = get_macd_signal(df, len(df) - 1)
    
    # Weekly volume analysis
    spike_ratio = latest.volume / latest.vol_avg if latest.vol_avg else 0
    volume_color = get_volume_color(df, len(df) - 1)
    volume_spike = ""
    
    if spike_ratio > 3:
        if volume_color == "green":
            volume_spike = "📊🟢 Weekly Volume: 🚨 MAJOR BUYING"
        elif volume_color == "red":
            volume_spike = "📊🔴 Weekly Volume: 🚨 MAJOR SELLING"
    elif spike_ratio > 2:
        if volume_color == "green":
            volume_spike = "📊🟢 Weekly Volume: ⚠️ Strong Buying"
        elif volume_color == "red":
            volume_spike = "📊🔴 Weekly Volume: ⚠️ Strong Selling"
    
    # RSI momentum
    rsi_change = latest.rsi - prev.rsi
    rsi_momentum = ""
    if abs(rsi_change) > 10:
        direction = "↗️ Accelerating" if rsi_change > 0 else "↘️ Decelerating"
        rsi_momentum = f"RSI {direction}"
    
    # Build signal parts
    parts = [flag, trend, price_vs_sma8, price_vs_sma21, price_vs_sma55]
    
    # Add SMA144 and SMA233 if they exist
    if price_vs_sma144:
        parts.append(price_vs_sma144)
    if price_vs_sma233:
        parts.append(price_vs_sma233)
        
    if crossover:
        parts.append(crossover)
    if price_cross:
        parts.append(price_cross)
    if macd_signal:
        parts.append(macd_signal)
    if volume_spike:
        parts.append(volume_spike)
    parts.append(rsi_desc)
    if rsi_momentum:
        parts.append(rsi_momentum)
    
    return " | ".join(parts)

# --- RSI DESCRIPTION (adjusted for weekly) ---
def describe_rsi(rsi_value):
    # Slightly different thresholds for weekly timeframe
    if rsi_value < 25:  # More extreme for weekly
        return "🟢 RSI OVERSOLD"
    elif rsi_value < 35:
        return "🟡 RSI Near Oversold"
    elif rsi_value <= 65:
        return "⚪️ RSI Neutral"
    elif rsi_value <= 75:
        return "🟡 RSI Near Overbought"
    else:
        return "🔴 RSI OVERBOUGHT"

# --- INDICATORS ---
def add_indicators(weekly_df):
    """Add indicators optimized for weekly timeframe with Fibonacci SMAs"""
    try:
        # Ensure we have enough data for each indicator
        if len(weekly_df) < 8:
            logging.warning(f"Insufficient data for SMA8: {len(weekly_df)} weeks")
            return weekly_df
            
        weekly_df['sma8'] = ta.trend.sma_indicator(weekly_df['close'], window=8)
        
        if len(weekly_df) >= 21:
            weekly_df['sma21'] = ta.trend.sma_indicator(weekly_df['close'], window=21)
        else:
            weekly_df['sma21'] = ta.trend.sma_indicator(weekly_df['close'], window=min(len(weekly_df)-1, 14))
            
        # Handle SMA55 with fallback
        if len(weekly_df) >= 55:
            weekly_df['sma55'] = ta.trend.sma_indicator(weekly_df['close'], window=55)
            weekly_df['sma_period'] = 55
        else:
            fallback_period = min(34, len(weekly_df)-1)
            weekly_df['sma55'] = ta.trend.sma_indicator(weekly_df['close'], window=fallback_period)
            weekly_df['sma_period'] = fallback_period
            
        # Add SMA144 (only if enough data)
        if len(weekly_df) >= 144:
            weekly_df['sma144'] = ta.trend.sma_indicator(weekly_df['close'], window=144)
        else:
            weekly_df['sma144'] = None  # Explicitly set to None if not enough data
            
        # Add SMA233 (only if enough data) 
        if len(weekly_df) >= 233:
            weekly_df['sma233'] = ta.trend.sma_indicator(weekly_df['close'], window=233)
        else:
            weekly_df['sma233'] = None  # Explicitly set to None if not enough data
            
        # RSI - needs at least 15 periods
        if len(weekly_df) >= 15:
            weekly_df['rsi'] = ta.momentum.rsi(weekly_df['close'], window=14)
        else:
            # Use shorter RSI window for limited data
            weekly_df['rsi'] = ta.momentum.rsi(weekly_df['close'], window=min(len(weekly_df)-1, 7))
            
        weekly_df['vol_avg'] = weekly_df['volume'].ewm(span=min(10, len(weekly_df)), adjust=False).mean()
        
        # MACD - needs at least 35 periods ideally
        if len(weekly_df) >= 35:
            macd = ta.trend.MACD(weekly_df['close'], window_slow=52, window_fast=26, window_sign=18)
            weekly_df['macd'] = macd.macd()
            weekly_df['macd_signal'] = macd.macd_signal()
            weekly_df['macd_histogram'] = macd.macd_diff()
        else:
            # Simplified MACD for limited data
            macd = ta.trend.MACD(weekly_df['close'], window_slow=20, window_fast=8, window_sign=6)
            weekly_df['macd'] = macd.macd()
            weekly_df['macd_signal'] = macd.macd_signal()
            weekly_df['macd_histogram'] = macd.macd_diff()
            
        return weekly_df
        
    except Exception as e:
        logging.error(f"Error adding indicators: {e}")
        return weekly_df
    
# --- ANALYSE ASSET ---
def analyse_asset(symbol, weekly_df, is_crypto, prev_signals, new_signals, new_alerts, html_results=None):
    """Main analysis function - analyzes weekly data and collects both text alerts and HTML data"""
    try:
        # Add indicators first
        weekly_df = add_indicators(weekly_df)
        
        if len(weekly_df) < 55:
            logging.info(f"{symbol}: Limited data ({len(weekly_df)} weeks), using shorter timeframe analysis")
        
        essential_cols = ['close', 'sma8', 'sma21', 'rsi']
        weekly_df = weekly_df.dropna(subset=essential_cols)
        
        if len(weekly_df) < 2:
            logging.warning(f"{symbol}: Not enough data after cleaning ({len(weekly_df)} weeks).")
            return
        
        latest, prev = weekly_df.iloc[-1], weekly_df.iloc[-2]
        
        if not hasattr(latest, 'rsi') or pd.isna(latest.rsi):
            logging.error(f"{symbol}: RSI not available.")
            return
        
        rsi_desc = describe_rsi(latest.rsi)
        new_signal_raw = generate_signal(weekly_df, latest, prev, rsi_desc)
        
        old_signal = prev_signals.get(symbol)
        full_signal = diff_signal_parts(old_signal, new_signal_raw)
        new_signals[symbol] = new_signal_raw
        
        # Generate text output for console logging
        output = format_output(symbol, latest, prev, full_signal, rsi_desc, is_crypto)
        logging.info(output)
        
        # Add to alerts if signal changed
        if old_signal != new_signal_raw:
            new_alerts.append(output)
        
        # Collect HTML data if html_results list is provided
        if html_results is not None:
            html_data = format_output(symbol, latest, prev, full_signal, rsi_desc, is_crypto)
            html_results.append(html_data)
        
    except Exception as e:
        logging.error(f"Error analyzing {symbol}: {str(e)}")
        import traceback
        logging.debug(f"Full traceback for {symbol}: {traceback.format_exc()}")
        return