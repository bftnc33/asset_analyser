import logging
import ta

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
               (('Daily UP' in new_item or 'Daily DOWN' in new_item) and ('Daily UP' in old_item or 'Daily DOWN' in old_item)) or \
               (('ABOVE SMA7' in new_item or 'BELOW SMA7' in new_item) and ('ABOVE SMA7' in old_item or 'BELOW SMA7' in old_item)) or \
               (('ABOVE SMA30' in new_item or 'BELOW SMA30' in new_item) and ('ABOVE SMA30' in old_item or 'BELOW SMA30' in old_item)) or \
               (('RSI' in new_item and 'RSI' in old_item)) or \
               (('MACD' in new_item and 'MACD' in old_item)):  # Added MACD change detection
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
    above_sma7 = "✅" if any("Price ABOVE SMA7" in part for part in current_parts) else "🔻"
    above_sma30 = "✅" if any("Price ABOVE SMA30" in part for part in current_parts) else "🔻"
    above_sma200 = "✅" if any("Price ABOVE SMA200" in part for part in current_parts) else "🔻"
    
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
        two_days_ago = df.iloc[latest_idx - 2]
        
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
        
        # Priority 2: Strong momentum signals
        elif macd_above_signal and current.macd_histogram > 0:
            if current.macd_histogram > previous.macd_histogram * 1.5:
                return "🔥 MACD Strong Bull"
        elif not macd_above_signal and current.macd_histogram < 0:
            if current.macd_histogram < previous.macd_histogram * 1.5:
                return "🔻 MACD Strong Bear"
        
        # Priority 3: Two-part MACD system (this should always execute if no crossover/strong signal)
        position_indicator = "✅" if macd_above_signal else "🔻"
        momentum_indicator = "⬆️" if macd_momentum_up else "⬇️"
        
        result = f"{position_indicator}{momentum_indicator} MACD"
        return result
        
    except Exception as e:
        print(f"ERROR in get_macd_signal: {e}")
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
            flag = "📈 Bull Flag (Below 200MA)"
    else:
        if latest.close > sma200:
            flag = "📉 Bear Flag (Above 200MA)"
        else:
            flag = "📉 Bear Flag (Below 200MA)"

    trend = "🔼 Daily UP" if latest.close > prev.close else "🔽 Daily DOWN"
    price_vs_sma7 = "✅ Price ABOVE SMA7" if latest.close > sma7 else "🔻 Price BELOW SMA7" 
    price_vs_sma30 = "✅ Price ABOVE SMA30" if latest.close > sma30 else "🔻 Price BELOW SMA30"
    price_vs_sma200 = "✅ Price ABOVE SMA200" if latest.close > sma200 else "🔻 Price BELOW SMA200"

    # SMA7 and SMA30 crossover detection
    crossover = ""
    if prev_sma7 < prev_sma30 and sma7 > sma30:
        crossover = "✨ Golden Cross (SMA7 ↑ SMA30)"
    elif prev_sma7 > prev_sma30 and sma7 < sma30:
        crossover = "⚠️ Death Cross (SMA7 ↓ SMA30)"
    
    # SMA200 crossover detection
    sma200_cross = ""
    if prev.close <= prev_sma200 and latest.close > sma200:
        sma200_cross = "🚀 Price crossed ABOVE 200MA"
    elif prev.close >= prev_sma200 and latest.close < sma200:
        sma200_cross = "💥 Price crossed BELOW 200MA"

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

    return " | ".join(parts)

# --- RSI DESCRIPTION ---
def describe_rsi(rsi_value):
    if rsi_value < 30:
        return "🟢 RSI OVERSOLD"
    elif rsi_value < 40:
        return "🟡 RSI Near Oversold"
    elif rsi_value <= 60:
        return "⚪️ RSI Neutral"
    elif rsi_value <= 70:
        return "🟡 RSI Near Overbought"
    else:
        return "🔴 RSI OVERBOUGHT"

# --- INDICATORS ---
def add_indicators(df):
    df['sma7'] = ta.trend.sma_indicator(df['close'], window=7)
    df['sma30'] = ta.trend.sma_indicator(df['close'], window=30)
    df['sma200'] = ta.trend.sma_indicator(df['close'], window=200)
    df['rsi'] = ta.momentum.rsi(df['close'], window=14)
    df['vol_avg'] = df['volume'].ewm(span=20, adjust=False).mean()
    
    # Add MACD
    macd = ta.trend.MACD(df['close'])
    df['macd'] = macd.macd()
    df['macd_signal'] = macd.macd_signal()
    df['macd_histogram'] = macd.macd_diff()

    return df

# --- ANALYSE ASSET ---
def analyse_asset(symbol, df, is_crypto, prev_signals, new_signals, new_alerts):
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