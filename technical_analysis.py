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
    above_sma8 = "✅" if any(part == "✅ Price ABOVE SMA8" for part in current_parts) else "🔻"
    above_sma21 = "✅" if any(part == "✅ Price ABOVE SMA21" for part in current_parts) else "🔻"
    above_sma55 = "✅" if any(part == "✅ Price ABOVE SMA55" for part in current_parts) else "🔻"

    # Add MACD status
    macd_status = ""
    for part in current_parts:
        if "🚀 MACD Bullish Cross" in part:
            macd_status = "🚀"
            break
        elif "⚠️ MACD Bearish Cross" in part:
            macd_status = "⚠️"
            break
        elif "🔥 MACD Strong Bull" in part:
            macd_status = "🔥"
            break
        elif "🔻 MACD Strong Bear" in part:
            macd_status = "🔻"
            break
        elif "✅⬆️ MACD" in part:
            macd_status = "✅⬆️"
            break
        elif "✅⬇️ MACD" in part:
            macd_status = "✅⬇️"
            break
        elif "🔻⬆️ MACD" in part:
            macd_status = "🔻⬆️"
            break
        elif "🔻⬇️ MACD" in part:
            macd_status = "🔻⬇️"
            break

    # RSI with momentum arrow if accelerating
    rsi_arrow = ""
    if any("RSI ↗️ Accelerating" in part for part in current_parts):
        rsi_arrow = "↗️"
    elif any("RSI ↘️ Decelerating" in part for part in current_parts):
        rsi_arrow = "↘️"

    rsi_status = f"RSI:{latest.rsi:.0f}{rsi_arrow}"

    # Build main status line
    actual_sma_period = latest.sma_period if hasattr(latest, 'sma_period') else 55
    status_parts = [flag, f"{above_sma8}SMA8", f"{above_sma21}SMA21", f"{above_sma55}SMA{actual_sma_period}"]
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
            if "ABOVE SMA8" in part and "was: 🔻 Price BELOW SMA8" in part:
                key_changes.append("✅ Broke ABOVE SMA8")
            elif "BELOW SMA8" in part and "was: ✅ Price ABOVE SMA8" in part:
                key_changes.append("🔻 Broke BELOW SMA8")
            elif "ABOVE SMA21" in part and "was: 🔻 Price BELOW SMA21" in part:
                key_changes.append("✅ Broke ABOVE SMA21")
            elif "BELOW SMA21" in part and "was: ✅ Price ABOVE SMA21" in part:
                key_changes.append("🔻 Broke BELOW SMA21")
            elif "ABOVE SMA55" in part and "was: 🔻 Price BELOW SMA55" in part:
                key_changes.append("✅ Broke ABOVE SMA55")
            elif "BELOW SMA55" in part and "was: ✅ Price ABOVE SMA55" in part:
                key_changes.append("🔻 Broke BELOW SMA55")
            elif "Bull Flag" in part and "was: 📉 Bear Flag" in part:
                key_changes.append("📈 Turned BULLISH")
            elif "Bear Flag" in part and "was: 📈 Bull Flag" in part:
                key_changes.append("📉 Turned BEARISH")
            elif "Weekly UP" in part and "was: 🔽 Weekly DOWN" in part:
                key_changes.append("🔼 Weekly UP")
            elif "Weekly DOWN" in part and "was: 🔼 Weekly UP" in part:
                key_changes.append("🔽 Weekly DOWN")
            elif "Golden Cross" in part:
                key_changes.append("✨ Golden Cross")
            elif "Death Cross" in part:
                key_changes.append("⚠️ Death Cross")
            elif "Major Bull Cross" in part:
                key_changes.append("🌟 Major Bull Cross (10>21>50)")
            elif "Major Bear Cross" in part:
                key_changes.append("💀 Major Bear Cross (10<21<50)")
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

    # Enhanced MACD change detection
    for part in current_parts:
        # Skip if we already have a MACD change message
        if any("MACD" in change for change in key_changes):
            continue
        if "🚀 MACD Bullish Cross" in part and not any("MACD" in change for change in key_changes):
            key_changes.append("🚀 MACD Bull Cross")
        elif "⚠️ MACD Bearish Cross" in part and not any("MACD" in change for change in key_changes):
            key_changes.append("⚠️ MACD Bear Cross")
        elif "🔥 MACD Strong Bull" in part:
            key_changes.append("🔥 MACD Strong Bull")
        elif "🔻 MACD Strong Bear" in part:
            key_changes.append("🔻 MACD Strong Bear")

    # Add current RSI conditions if extreme
    if "🟢 RSI OVERSOLD" in rsi_desc and not any("RSI" in change for change in key_changes):
        key_changes.append(f"🟢 RSI OVERSOLD ({latest.rsi:.0f})")
    elif "🔴 RSI OVERBOUGHT" in rsi_desc and not any("RSI" in change for change in key_changes):
        key_changes.append(f"🔴 RSI OVERBOUGHT ({latest.rsi:.0f})")
    elif "🟡 RSI Near Overbought" in rsi_desc and not any("RSI" in change for change in key_changes):
        key_changes.append(f"🟡 RSI heating up ({latest.rsi:.0f}→overbought)")
    elif "🟡 RSI Near Oversold" in rsi_desc and not any("RSI" in change for change in key_changes):
        key_changes.append(f"🟡 RSI cooling ({latest.rsi:.0f}→oversold)")

    # Return format: always show status line, add changes if any
    if key_changes:
        changes_line = f"   {' | '.join(key_changes)}"
        return f"{main_line}\n{changes_line}"
    else:
        return main_line

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
    
    # Comprehensive crossover detection system
    crossover = ""
    
    # Perfect Alignment Crosses (highest priority)
    if (prev_sma8 <= prev_sma21 or prev_sma21 <= prev_sma55) and \
       (sma8 > sma21 > sma55):
        crossover = "⭐ Perfect Bull Alignment (8>21>55>144>233)"
    elif (prev_sma8 >= prev_sma21 or prev_sma21 >= prev_sma55) and \
         (sma8 < sma21 < sma55):
        crossover = "💀 Perfect Bear Alignment (8<21<55)"
    
    # Major Bull Cross: 8 crosses above 21, and 21>55
    elif (prev_sma8 <= prev_sma21 and sma8 > sma21) and (sma21 > sma55):
        crossover = "🌟 Major Bull Cross (8↑21, Strong Trend)"
    # Major Bear Cross: 8 crosses below 21, and 21<55
    elif (prev_sma8 >= prev_sma21 and sma8 < sma21) and (sma21 < sma55):
        crossover = "💀 Major Bear Cross (8↓21, Strong Trend)"
    
    # Standard Golden Cross: 8 crosses above 21
    elif prev_sma8 <= prev_sma21 and sma8 > sma21:
        crossover = "✨ Golden Cross (SMA8 ↑ SMA21)"
    # Standard Death Cross: 8 crosses below 21
    elif prev_sma8 >= prev_sma21 and sma8 < sma21:
        crossover = "⚠️ Death Cross (SMA8 ↓ SMA21)"
    
    # Medium-term crosses
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
    
    # Weekly volume analysis (less emphasis than daily)
    spike_ratio = latest.volume / latest.vol_avg if latest.vol_avg else 0
    volume_color = get_volume_color(df, len(df) - 1)
    volume_spike = ""
    
    # Higher thresholds for weekly data
    if spike_ratio > 3:  # Much higher threshold for weekly
        if volume_color == "green":
            volume_spike = "📊🟢 Weekly Volume: 🚨 MAJOR BUYING"
        elif volume_color == "red":
            volume_spike = "📊🔴 Weekly Volume: 🚨 MAJOR SELLING"
    elif spike_ratio > 2:
        if volume_color == "green":
            volume_spike = "📊🟢 Weekly Volume: ⚠️ Strong Buying"
        elif volume_color == "red":
            volume_spike = "📊🔴 Weekly Volume: ⚠️ Strong Selling"
    
    # RSI momentum (weekly requires bigger changes)
    rsi_change = latest.rsi - prev.rsi
    rsi_momentum = ""
    if abs(rsi_change) > 10:  # Higher threshold for weekly
        direction = "↗️ Accelerating" if rsi_change > 0 else "↘️ Decelerating"
        rsi_momentum = f"RSI {direction}"
    
    # Build signal parts
    parts = [flag, trend, price_vs_sma8, price_vs_sma21, price_vs_sma55]
    
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
def analyse_asset(symbol, weekly_df, is_crypto, prev_signals, new_signals, new_alerts):
    """Main analysis function - analyzes weekly data directly"""
    try:
        # Add indicators first
        weekly_df = add_indicators(weekly_df)
        
        # Check we have enough data BEFORE dropping NaN values
        if len(weekly_df) < 55:
            logging.info(f"{symbol}: Limited data ({len(weekly_df)} weeks), using shorter timeframe analysis")
        
        # More selective dropna - only drop rows where essential indicators are missing
        essential_cols = ['close', 'sma8', 'sma21', 'rsi']
        weekly_df = weekly_df.dropna(subset=essential_cols)
        
        if len(weekly_df) < 2:
            logging.warning(f"{symbol}: Not enough data after cleaning ({len(weekly_df)} weeks).")
            return
            
        # Debug: Check what columns we actually have
        logging.debug(f"{symbol}: Available columns: {weekly_df.columns.tolist()}")
        
        latest, prev = weekly_df.iloc[-1], weekly_df.iloc[-2]
        
        # Debug: Check if RSI exists
        if not hasattr(latest, 'rsi') or pd.isna(latest.rsi):
            logging.error(f"{symbol}: RSI not available. Latest row data: {latest.index.tolist()}")
            return
            
        rsi_desc = describe_rsi(latest.rsi)
        new_signal_raw = generate_signal(weekly_df, latest, prev, rsi_desc)
        
        old_signal = prev_signals.get(symbol)
        full_signal = diff_signal_parts(old_signal, new_signal_raw)
        
        new_signals[symbol] = new_signal_raw
        output = format_output(symbol, latest, prev, full_signal, rsi_desc, is_crypto)
        logging.info(output)
        
        if old_signal != new_signal_raw:
            new_alerts.append(output)
            
    except Exception as e:
        logging.error(f"Error analyzing {symbol}: {str(e)}")
        import traceback
        logging.debug(f"Full traceback for {symbol}: {traceback.format_exc()}")
        return