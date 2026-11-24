import logging
import ta
import pandas as pd

# --- Setup Logging ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

# --- SMA200 COLOUR HELPER ---

def sma200_distance_colour(distance_pct):
    """
    Return an RGB CSS colour string scaled by distance from SMA200.

    Above SMA200 (positive distance) → green shades.
    Below SMA200 (negative distance) → red shades.
    At SMA200 (zero)                 → neutral light grey.

    Intensity scales linearly from 0% to CAP_PCT distance,
    clamped so it never exceeds the darkest shade.

    Returns a tuple of (background_colour, text_colour) CSS strings.
    """
    CAP_PCT = 20.0  # distance at which colour reaches maximum saturation

    intensity = min(abs(distance_pct) / CAP_PCT, 1.0)

    if distance_pct > 0:
        # Green: interpolate from near-white (#f0fff0) to dark green (#1a5c1a)
        r = int(240 - (240 - 26)  * intensity)   # 240 → 26
        g = int(255 - (255 - 92)  * intensity)   # 255 → 92
        b = int(240 - (240 - 26)  * intensity)   # 240 → 26
    elif distance_pct < 0:
        # Red: interpolate from near-white (#fff0f0) to dark red (#5c1a1a)
        r = int(255 - (255 - 92)  * intensity)   # 255 → 92
        g = int(240 - (240 - 26)  * intensity)   # 240 → 26
        b = int(240 - (240 - 26)  * intensity)   # 240 → 26
    else:
        r, g, b = 245, 245, 245  # neutral grey

    bg_colour = f"rgb({r},{g},{b})"

    # Switch text to white once background is dark enough
    text_colour = "white" if intensity > 0.55 else "#1a1a1a"

    return bg_colour, text_colour


def format_asset_html(main_line, changes_line, distance_pct):
    """
    Wrap a single asset's output in a colour-coded HTML block.
    """
    bg, text = sma200_distance_colour(distance_pct)
    changes_html = (
        f'<div style="font-size:0.85em; margin-top:4px; opacity:0.9;">'
        f'{changes_line.strip()}</div>'
        if changes_line else ""
    )
    return (
        f'<div style="'
        f'background-color:{bg}; color:{text}; '
        f'padding:10px 14px; margin:4px 0; '
        f'border-radius:6px; font-family:monospace; font-size:0.95em;'
        f'">'
        f'{main_line}'
        f'{changes_html}'
        f'</div>'
    )


# --- DIFFERENCE CHECK ---
def diff_signal_parts(old_signal, new_signal):
    if not old_signal:
        return new_signal

    def extract_items(text):
        clean_text = (
            text.split("↪️ Changes:")[0].strip()
            if "↪️ Changes:" in text else text
        )
        return [part.strip() for part in clean_text.split("|") if part.strip()]

    old_items = set(extract_items(old_signal))
    new_items_list = extract_items(new_signal)
    new_items_set = set(new_items_list)
    removed = old_items - new_items_set

    enhanced_signal_parts = []
    for new_item in new_items_list:
        enhanced_part = new_item
        for old_item in removed:
            if (
                ("Bull Flag" in new_item or "Bear Flag" in new_item)
                and ("Bull Flag" in old_item or "Bear Flag" in old_item)
            ) or (
                ("Weekly UP" in new_item or "Weekly DOWN" in new_item)
                and ("Weekly UP" in old_item or "Weekly DOWN" in old_item)
            ) or (
                ("ABOVE SMA200" in new_item or "BELOW SMA200" in new_item)
                and ("ABOVE SMA200" in old_item or "BELOW SMA200" in old_item)
            ) or (
                "SMA200 Distance" in new_item and "SMA200 Distance" in old_item
            ) or (
                "RSI" in new_item and "RSI" in old_item
            ):
                enhanced_part = f"{new_item} (was: {old_item})"
                break
        enhanced_signal_parts.append(enhanced_part)

    return " | ".join(enhanced_signal_parts)


# --- FORMAT OUTPUT ---
def format_output(symbol, latest, previous, signal, is_crypto):
    # Determine currency and formatting
    if (symbol.endswith("/BTC") or symbol.endswith("BTC")) and is_crypto:
        currency = "₿"
        suffix = ""
        price_fmt = "{:,.6f}" if latest.close < 0.01 else "{:,.4f}"
        current_close = latest.close
        previous_close = previous.close
    elif symbol.endswith(("SGLN.L", "SSLN.L")):
        currency = "£"
        suffix = ""
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
        currency = "£"
        suffix = ""
        price_fmt = "{:,.4f}" if latest.close < 1 else "{:,.2f}"
        current_close = latest.close
        previous_close = previous.close
    else:
        currency = "$"
        suffix = ""
        price_fmt = "{:,.4f}" if latest.close < 1 else "{:,.2f}"
        current_close = latest.close
        previous_close = previous.close

    price_change = ((current_close - previous_close) / previous_close) * 100
    change_color = (
        "🟢" if price_change > 0 else "🔴" if price_change < 0 else "⚪️"
    )

    signal_parts = signal.split(" | ")

    def extract_current_status(part):
        if "(was:" in part:
            return part.split("(was:")[0].strip()
        return part.strip()

    current_parts = [extract_current_status(p) for p in signal_parts]

    # Bull / bear derived purely from price vs SMA200
    if any("Bull Flag" in p for p in current_parts):
        flag = "📈 Bull"
    elif any("Bear Flag" in p for p in current_parts):
        flag = "📉 Bear"
    else:
        flag = "⚪️ Unknown"

    # SMA200 position indicator
    above_sma200 = (
        "✅" if any(p == "✅ Price ABOVE SMA200" for p in current_parts)
        else "🔻"
    )

    # SMA200 distance — extract raw float for colour calculation
    sma200_dist_str = ""
    sma200_distance_pct = 0.0
    for p in current_parts:
        if "SMA200 Distance" in p:
            sma200_dist_str = p
            try:
                # e.g. "SMA200 Distance: +12.3%"
                sma200_distance_pct = float(
                    p.split(":")[1].strip().rstrip("%")
                )
            except (IndexError, ValueError):
                sma200_distance_pct = 0.0
            break

    # RSI with momentum arrow
    rsi_arrow = ""
    if any("RSI ↗️ Accelerating" in p for p in current_parts):
        rsi_arrow = "↗️"
    elif any("RSI ↘️ Decelerating" in p for p in current_parts):
        rsi_arrow = "↘️"
    rsi_status = f"RSI:{latest.rsi:.0f}{rsi_arrow}"

    status_parts = [flag, f"{above_sma200}SMA200", sma200_dist_str, rsi_status]
    status_parts = [p for p in status_parts if p]

    main_line = (
        f"{symbol}: {currency}{price_fmt.format(current_close)}{suffix} "
        f"{change_color}{price_change:+.1f}% | {' | '.join(status_parts)}"
    )

    # Key changes
    key_changes = []
    for part in signal_parts:
        part = part.strip()
        current = part.split("(was:")[0].strip()

        if "(was:" in part:
            was_part = part.split("(was:")[1]
            if "ABOVE SMA200" in current and "BELOW SMA200" in was_part:
                key_changes.append("✅ Broke ABOVE SMA200")
            elif "BELOW SMA200" in current and "ABOVE SMA200" in was_part:
                key_changes.append("🔻 Broke BELOW SMA200")
            elif "Bull Flag" in current and "Bear Flag" in was_part:
                key_changes.append("📈 Turned BULLISH")
            elif "Bear Flag" in current and "Bull Flag" in was_part:
                key_changes.append("📉 Turned BEARISH")
            elif "Weekly UP" in current and "Weekly DOWN" in was_part:
                key_changes.append("🔼 Weekly UP")
            elif "Weekly DOWN" in current and "Weekly UP" in was_part:
                key_changes.append("🔽 Weekly DOWN")
            elif "RSI" in current:
                if "OVERSOLD" in current:
                    key_changes.append(f"🟢 RSI OVERSOLD ({latest.rsi:.0f})")
                elif "OVERBOUGHT" in current:
                    key_changes.append(f"🔴 RSI OVERBOUGHT ({latest.rsi:.0f})")
                elif "Near Overbought" in current:
                    key_changes.append(
                        f"🟡 RSI heating up ({latest.rsi:.0f}→overbought)"
                    )
                elif "Near Oversold" in current:
                    key_changes.append(
                        f"🟡 RSI cooling ({latest.rsi:.0f}→oversold)"
                    )

    changes_line = f" {' | '.join(key_changes)}" if key_changes else ""

    # Log plain text version
    plain = f"{main_line}\n{changes_line}" if changes_line else main_line
    logging.info(plain)

    return format_asset_html(main_line, changes_line, sma200_distance_pct)


# --- VOLUME COLOR DETECTION ---
def get_volume_color(df, latest_idx):
    """Determine if volume candle is green (buying) or red (selling)"""
    if latest_idx < 1:
        return "neutral"
    current = df.iloc[latest_idx]
    previous = df.iloc[latest_idx - 1]
    if current.close > previous.close:
        return "green"
    elif current.close < previous.close:
        return "red"
    else:
        return "neutral"


# --- SIGNAL GENERATION ---
def generate_signal(df, latest, prev):
    sma200 = latest.sma200

    if latest.close > sma200:
        flag = "📈 Bull Flag (Price ABOVE SMA200)"
    else:
        flag = "📉 Bear Flag (Price BELOW SMA200)"

    price_vs_sma200 = (
        "✅ Price ABOVE SMA200" if latest.close > sma200
        else "🔻 Price BELOW SMA200"
    )

    sma200_distance = ((latest.close - sma200) / sma200) * 100
    dist_sign = "+" if sma200_distance >= 0 else ""
    sma200_dist_str = f"SMA200 Distance: {dist_sign}{sma200_distance:.1f}%"

    trend = (
        "🔼 Weekly UP" if latest.close > prev.close else "🔽 Weekly DOWN"
    )

    spike_ratio = latest.volume / latest.vol_avg if latest.vol_avg else 0
    volume_color = get_volume_color(df, len(df) - 1)
    volume_spike = ""
    if spike_ratio > 2.5:
        if volume_color == "green":
            volume_spike = "📊🟢 Weekly Volume: 🚨 MAJOR BUYING"
        elif volume_color == "red":
            volume_spike = "📊🔴 Weekly Volume: 🚨 MAJOR SELLING"
    elif spike_ratio > 1.5:
        if volume_color == "green":
            volume_spike = "📊🟢 Weekly Volume: ⚠️ Strong Buying"
        elif volume_color == "red":
            volume_spike = "📊🔴 Weekly Volume: ⚠️ Strong Selling"

    rsi_change = latest.rsi - prev.rsi
    rsi_momentum = ""
    if abs(rsi_change) > 5:
        direction = "↗️ Accelerating" if rsi_change > 0 else "↘️ Decelerating"
        rsi_momentum = f"RSI {direction}"

    parts = [flag, trend, price_vs_sma200, sma200_dist_str]
    if volume_spike:
        parts.append(volume_spike)
    if rsi_momentum:
        parts.append(rsi_momentum)

    return " | ".join(parts)


# --- INDICATORS ---
def add_indicators(df):
    """Add SMA200, RSI, and volume average for weekly timeframe."""
    try:
        if len(df) < 200:
            logging.warning(
                f"Insufficient data for SMA200: {len(df)} rows available. "
                f"Need at least 200 weekly candles (~4 years)."
            )
            return df

        df["sma200"] = ta.trend.sma_indicator(df["close"], window=200)

        if len(df) >= 15:
            df["rsi"] = ta.momentum.rsi(df["close"], window=14)
        else:
            df["rsi"] = ta.momentum.rsi(
                df["close"], window=min(len(df) - 1, 7)
            )

        df["vol_avg"] = df["volume"].ewm(
            span=min(10, len(df)), adjust=False
        ).mean()

        return df

    except Exception as e:
        logging.error(f"Error adding indicators: {e}")
        return df


# --- ANALYSE ASSET ---
def analyse_asset(
    symbol, df, is_crypto, prev_signals, new_signals, new_alerts
):
    """Main analysis function - analyses weekly data."""
    try:
        df = add_indicators(df)

        if len(df) < 200:
            logging.info(
                f"{symbol}: Insufficient data for SMA200 "
                f"({len(df)} weekly candles, need 200)."
            )
            return

        essential_cols = ["close", "sma200", "rsi"]
        df = df.dropna(subset=essential_cols)

        if len(df) < 2:
            logging.warning(
                f"{symbol}: Not enough data after cleaning ({len(df)} rows)."
            )
            return

        logging.debug(f"{symbol}: Available columns: {df.columns.tolist()}")

        latest, prev = df.iloc[-1], df.iloc[-2]

        if not hasattr(latest, "rsi") or pd.isna(latest.rsi):
            logging.error(
                f"{symbol}: RSI not available. "
                f"Latest row data: {latest.index.tolist()}"
            )
            return

        new_signal_raw = generate_signal(df, latest, prev)

        old_signal = prev_signals.get(symbol)
        full_signal = diff_signal_parts(old_signal, new_signal_raw)

        new_signals[symbol] = new_signal_raw

        output = format_output(symbol, latest, prev, full_signal, is_crypto)
        new_alerts.append(output)

    except Exception as e:
        logging.error(f"Error analyzing {symbol}: {str(e)}")
        import traceback
        logging.debug(
            f"Full traceback for {symbol}: {traceback.format_exc()}"
        )
        return