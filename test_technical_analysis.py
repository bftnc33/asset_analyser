"""
Tests for technical_analysis.py.

Covers: diff_signal_parts, format_output, get_volume_color,
        generate_signal (flags, crossovers, volume, RSI momentum,
        price crosses), add_indicators, and analyse_asset.
"""

import pandas as pd
import numpy as np
import pytest
from types import SimpleNamespace
from unittest.mock import patch
from technical_analysis import (
    diff_signal_parts,
    format_output,
    get_volume_color,
    generate_signal,
    add_indicators,
    analyse_asset,
)


# ===========================================================================
# Shared helpers
# ===========================================================================

def make_row(close, sma8, sma21, sma55, rsi=50.0, volume=1000, vol_avg=1000):
    return SimpleNamespace(
        close=close, sma8=sma8, sma21=sma21, sma55=sma55,
        rsi=rsi, volume=volume, vol_avg=vol_avg,
    )


def make_df(closes, volumes=None):
    """Build a minimal DataFrame from a list of close prices."""
    if volumes is None:
        volumes = [1000] * len(closes)
    return pd.DataFrame({"close": closes, "volume": volumes})


def signal_parts(latest, prev):
    df = make_df([prev.close, latest.close])
    raw = generate_signal(df, latest, prev)
    return set(part.strip() for part in raw.split("|"))


def make_format_row(close, rsi=50.0):
    """Minimal row for format_output (only close and rsi needed)."""
    return SimpleNamespace(close=close, rsi=rsi)


# ===========================================================================
# diff_signal_parts
# ===========================================================================

class TestDiffSignalParts:
    def test_no_old_signal_returns_new(self):
        assert diff_signal_parts(None, "A | B | C") == "A | B | C"

    def test_empty_old_signal_returns_new(self):
        assert diff_signal_parts("", "A | B") == "A | B"

    def test_unchanged_signal_has_no_was_annotation(self):
        signal = "📈 Bull Flag | 🔼 Daily UP | ✅ Price ABOVE SMA8"
        result = diff_signal_parts(signal, signal)
        assert "(was:" not in result

    def test_flag_change_annotated(self):
        old = "📈 Bull Flag (Perfect Fibonacci Alignment) | 🔼 Daily UP"
        new = "📉 Bear Flag (Perfect Fibonacci Alignment) | 🔼 Daily UP"
        result = diff_signal_parts(old, new)
        assert "(was:" in result
        assert "Bear Flag" in result

    def test_sma8_change_annotated(self):
        old = "📈 Bull Flag | 🔻 Price BELOW SMA8"
        new = "📈 Bull Flag | ✅ Price ABOVE SMA8"
        result = diff_signal_parts(old, new)
        assert "(was:" in result
        assert "ABOVE SMA8" in result

    def test_sma21_change_annotated(self):
        old = "📈 Bull Flag | ✅ Price ABOVE SMA21"
        new = "📈 Bull Flag | 🔻 Price BELOW SMA21"
        result = diff_signal_parts(old, new)
        assert "(was:" in result
        assert "BELOW SMA21" in result

    def test_sma55_change_annotated(self):
        old = "📈 Bull Flag | 🔻 Price BELOW SMA55"
        new = "📈 Bull Flag | ✅ Price ABOVE SMA55"
        result = diff_signal_parts(old, new)
        assert "(was:" in result

    def test_daily_trend_change_annotated(self):
        old = "📈 Bull Flag | 🔼 Daily UP"
        new = "📈 Bull Flag | 🔽 Daily DOWN"
        result = diff_signal_parts(old, new)
        assert "(was:" in result

    def test_strips_existing_changes_section_from_old(self):
        old = "📈 Bull Flag | 🔼 Daily UP ↪️ Changes: something"
        new = "📈 Bull Flag | 🔽 Daily DOWN"
        result = diff_signal_parts(old, new)
        assert "↪️ Changes:" not in result


# ===========================================================================
# format_output  — currency / price formatting
# ===========================================================================

class TestFormatOutputCurrency:
    BASE_SIGNAL = "📈 Bull Flag (Perfect Fibonacci Alignment) | 🔼 Daily UP | ✅ Price ABOVE SMA8 | ✅ Price ABOVE SMA21 | ✅ Price ABOVE SMA55"

    def _fmt(self, symbol, close, prev_close=None, is_crypto=False, rsi=50.0):
        if prev_close is None:
            prev_close = close * 0.99
        latest   = make_format_row(close, rsi)
        previous = make_format_row(prev_close, rsi)
        return format_output(symbol, latest, previous, self.BASE_SIGNAL, is_crypto)

    def test_us_stock_uses_dollar(self):
        result = self._fmt("AAPL", 150.0, 148.0, is_crypto=False)
        assert "$" in result
        assert "£" not in result
        assert "₿" not in result

    def test_crypto_uses_pound(self):
        result = self._fmt("BTC/GBP", 50000.0, 49000.0, is_crypto=True)
        assert "£" in result

    def test_btc_quoted_crypto_uses_btc_symbol(self):
        result = self._fmt("ETH/BTC", 0.027, 0.026, is_crypto=True)
        assert "₿" in result
        assert "£" not in result

    def test_london_stock_uses_pound(self):
        result = self._fmt("BARC.L", 200.0, 198.0, is_crypto=False)
        assert "£" in result

    def test_pence_stock_divides_by_100(self):
        # SGLN.L prices are in pence — should display as pounds
        result = self._fmt("SGLN.L", 2750, 2700, is_crypto=False)
        assert "£" in result
        assert "27" in result   # 2750p → ~£27.50

    def test_price_up_shows_green(self):
        result = self._fmt("AAPL", 150.0, 140.0)
        assert "🟢" in result

    def test_price_down_shows_red(self):
        result = self._fmt("AAPL", 140.0, 150.0)
        assert "🔴" in result

    def test_price_unchanged_shows_white(self):
        result = self._fmt("AAPL", 150.0, 150.0)
        assert "⚪️" in result

    def test_symbol_in_output(self):
        result = self._fmt("TSLA", 200.0)
        assert "TSLA" in result


class TestFormatOutputFlags:
    def _fmt(self, signal, close=100.0, rsi=50.0):
        latest   = make_format_row(close, rsi)
        previous = make_format_row(close * 0.99, rsi)
        return format_output("TEST", latest, previous, signal, is_crypto=False)

    def test_bull_flag_shown(self):
        sig = "📈 Bull Flag (Perfect Fibonacci Alignment) | 🔼 Daily UP | ✅ Price ABOVE SMA8 | ✅ Price ABOVE SMA21 | ✅ Price ABOVE SMA55"
        assert "📈 Bull" in self._fmt(sig)

    def test_bear_flag_shown(self):
        sig = "📉 Bear Flag (Perfect Fibonacci Alignment) | 🔽 Daily DOWN | 🔻 Price BELOW SMA8 | 🔻 Price BELOW SMA21 | 🔻 Price BELOW SMA55"
        assert "📉 Bear" in self._fmt(sig)

    def test_mixed_signals_shown(self):
        sig = "⚪️ Mixed Signals | 🔼 Daily UP | ✅ Price ABOVE SMA8 | 🔻 Price BELOW SMA21 | 🔻 Price BELOW SMA55"
        assert "⚪️ Mixed" in self._fmt(sig)

    def test_rsi_accelerating_arrow(self):
        sig = "📈 Bull Flag (Perfect Fibonacci Alignment) | 🔼 Daily UP | ✅ Price ABOVE SMA8 | ✅ Price ABOVE SMA21 | ✅ Price ABOVE SMA55 | RSI ↗️ Accelerating"
        assert "↗️" in self._fmt(sig)

    def test_rsi_decelerating_arrow(self):
        sig = "📈 Bull Flag (Perfect Fibonacci Alignment) | 🔼 Daily UP | ✅ Price ABOVE SMA8 | ✅ Price ABOVE SMA21 | ✅ Price ABOVE SMA55 | RSI ↘️ Decelerating"
        assert "↘️" in self._fmt(sig)


class TestFormatOutputKeyChanges:
    """format_output should emit a changes line when signal parts contain (was: ...)."""

    def _fmt_with_change(self, changed_part):
        signal = f"📈 Bull Flag (Perfect Fibonacci Alignment) | 🔼 Daily UP | {changed_part} | ✅ Price ABOVE SMA21 | ✅ Price ABOVE SMA55"
        latest   = make_format_row(100.0, rsi=50.0)
        previous = make_format_row(99.0,  rsi=50.0)
        return format_output("TEST", latest, previous, signal, is_crypto=False)

    def test_broke_above_sma8(self):
        result = self._fmt_with_change("✅ Price ABOVE SMA8 (was: 🔻 Price BELOW SMA8)")
        assert "Broke ABOVE SMA8" in result

    def test_broke_below_sma8(self):
        result = self._fmt_with_change("🔻 Price BELOW SMA8 (was: ✅ Price ABOVE SMA8)")
        assert "Broke BELOW SMA8" in result

    def test_broke_above_sma21(self):
        result = self._fmt_with_change("✅ Price ABOVE SMA21 (was: 🔻 Price BELOW SMA21)")
        assert "Broke ABOVE SMA21" in result

    def test_broke_below_sma21(self):
        result = self._fmt_with_change("🔻 Price BELOW SMA21 (was: ✅ Price ABOVE SMA21)")
        assert "Broke BELOW SMA21" in result

    def test_broke_above_sma55(self):
        result = self._fmt_with_change("✅ Price ABOVE SMA55 (was: 🔻 Price BELOW SMA55)")
        assert "Broke ABOVE SMA55" in result

    def test_broke_below_sma55(self):
        result = self._fmt_with_change("🔻 Price BELOW SMA55 (was: ✅ Price ABOVE SMA55)")
        assert "Broke BELOW SMA55" in result

    def test_turned_bullish(self):
        signal = "📈 Bull Flag (Perfect Fibonacci Alignment) (was: 📉 Bear Flag) | 🔼 Daily UP | ✅ Price ABOVE SMA8 | ✅ Price ABOVE SMA21 | ✅ Price ABOVE SMA55"
        latest   = make_format_row(100.0)
        previous = make_format_row(99.0)
        result = format_output("TEST", latest, previous, signal, is_crypto=False)
        assert "Turned BULLISH" in result

    def test_turned_bearish(self):
        signal = "📉 Bear Flag (Perfect Fibonacci Alignment) (was: 📈 Bull Flag) | 🔽 Daily DOWN | 🔻 Price BELOW SMA8 | 🔻 Price BELOW SMA21 | 🔻 Price BELOW SMA55"
        latest   = make_format_row(100.0)
        previous = make_format_row(101.0)
        result = format_output("TEST", latest, previous, signal, is_crypto=False)
        assert "Turned BEARISH" in result

    def test_golden_cross_change(self):
        signal = "📈 Bull Flag (Perfect Fibonacci Alignment) | 🔼 Daily UP | ✅ Price ABOVE SMA8 | ✅ Price ABOVE SMA21 | ✅ Price ABOVE SMA55 | ✨ Golden Cross (SMA8 ↑ SMA55) (was: ⚠️ Death Cross)"
        latest   = make_format_row(100.0)
        previous = make_format_row(99.0)
        result = format_output("TEST", latest, previous, signal, is_crypto=False)
        assert "Golden Cross" in result

    def test_no_changes_line_when_signal_unchanged(self):
        signal = "📈 Bull Flag (Perfect Fibonacci Alignment) | 🔼 Daily UP | ✅ Price ABOVE SMA8 | ✅ Price ABOVE SMA21 | ✅ Price ABOVE SMA55"
        latest   = make_format_row(100.0)
        previous = make_format_row(99.0)
        result = format_output("TEST", latest, previous, signal, is_crypto=False)
        assert "\n" not in result


# ===========================================================================
# get_volume_color
# ===========================================================================

class TestGetVolumeColor:
    def test_green_when_close_rises(self):
        df = make_df([100, 110])
        assert get_volume_color(df, 1) == "green"

    def test_red_when_close_falls(self):
        df = make_df([110, 100])
        assert get_volume_color(df, 1) == "red"

    def test_neutral_when_close_unchanged(self):
        df = make_df([100, 100])
        assert get_volume_color(df, 1) == "neutral"

    def test_neutral_when_idx_zero(self):
        df = make_df([100, 110])
        assert get_volume_color(df, 0) == "neutral"


# ===========================================================================
# generate_signal — flags, crossovers, volume spikes, RSI momentum
# ===========================================================================

class TestFlag:
    def test_bull_flag_when_8_gt_21_gt_55(self):
        latest = make_row(close=110, sma8=100, sma21=90, sma55=80)
        prev   = make_row(close=109, sma8=99,  sma21=91, sma55=81)
        assert any("Bull Flag" in p for p in signal_parts(latest, prev))

    def test_bear_flag_when_8_lt_21_lt_55(self):
        latest = make_row(close=70, sma8=80, sma21=90, sma55=100)
        prev   = make_row(close=71, sma8=81, sma21=91, sma55=101)
        assert any("Bear Flag" in p for p in signal_parts(latest, prev))

    def test_mixed_signals_when_not_aligned(self):
        latest = make_row(close=90, sma8=85, sma21=80, sma55=95)
        prev   = make_row(close=91, sma8=84, sma21=81, sma55=96)
        assert any("Mixed Signals" in p for p in signal_parts(latest, prev))


class TestCrossovers:
    def test_golden_cross(self):
        """sma8 crosses above sma55."""
        prev   = make_row(close=100, sma8=78, sma21=85, sma55=80)
        latest = make_row(close=110, sma8=83, sma21=85, sma55=80)
        assert any("Golden Cross" in p for p in signal_parts(latest, prev))

    def test_death_cross(self):
        """sma8 crosses below sma55."""
        prev   = make_row(close=100, sma8=82, sma21=85, sma55=80)
        latest = make_row(close=80,  sma8=77, sma21=85, sma55=80)
        assert any("Death Cross" in p for p in signal_parts(latest, prev))

    def test_no_crossover_sma21_crosses_sma55(self):
        """sma21 crossing sma55 alone does NOT trigger a crossover."""
        prev   = make_row(close=100, sma8=100, sma21=78, sma55=80)
        latest = make_row(close=110, sma8=100, sma21=82, sma55=80)
        assert not any("Cross" in p for p in signal_parts(latest, prev))

    def test_no_crossover_when_stable(self):
        prev   = make_row(close=100, sma8=100, sma21=90, sma55=80)
        latest = make_row(close=105, sma8=101, sma21=91, sma55=81)
        assert not any("Cross" in p for p in signal_parts(latest, prev))


class TestVolume:
    def _parts_with_volume(self, volume, vol_avg):
        prev   = make_row(close=100, sma8=100, sma21=90, sma55=80, volume=vol_avg,  vol_avg=vol_avg)
        latest = make_row(close=105, sma8=101, sma21=91, sma55=81, volume=volume, vol_avg=vol_avg)
        return signal_parts(latest, prev)

    def test_major_buying_volume(self):
        parts = self._parts_with_volume(volume=3000, vol_avg=1000)  # ratio 3.0 > 2.5, price up
        assert any("MAJOR BUYING" in p for p in parts)

    def test_major_selling_volume(self):
        prev   = make_row(close=105, sma8=100, sma21=90, sma55=80, volume=1000, vol_avg=1000)
        latest = make_row(close=100, sma8=101, sma21=91, sma55=81, volume=3000, vol_avg=1000)
        parts  = signal_parts(latest, prev)
        assert any("MAJOR SELLING" in p for p in parts)

    def test_strong_buying_volume(self):
        parts = self._parts_with_volume(volume=2000, vol_avg=1000)  # ratio 2.0, between 1.5-2.5
        assert any("Strong Buying" in p for p in parts)

    def test_strong_selling_volume(self):
        prev   = make_row(close=105, sma8=100, sma21=90, sma55=80, volume=1000, vol_avg=1000)
        latest = make_row(close=100, sma8=101, sma21=91, sma55=81, volume=2000, vol_avg=1000)
        parts  = signal_parts(latest, prev)
        assert any("Strong Selling" in p for p in parts)

    def test_normal_volume_no_spike(self):
        parts = self._parts_with_volume(volume=1100, vol_avg=1000)  # ratio 1.1
        assert not any("Volume" in p for p in parts)

    def test_zero_vol_avg_no_crash(self):
        """vol_avg of 0 should not raise ZeroDivisionError."""
        prev   = make_row(close=100, sma8=100, sma21=90, sma55=80, volume=1000, vol_avg=0)
        latest = make_row(close=105, sma8=101, sma21=91, sma55=81, volume=1000, vol_avg=0)
        parts  = signal_parts(latest, prev)
        assert isinstance(parts, set)


class TestRSIMomentum:
    def test_accelerating_rsi(self):
        prev   = make_row(close=100, sma8=100, sma21=90, sma55=80, rsi=40)
        latest = make_row(close=105, sma8=101, sma21=91, sma55=81, rsi=48)  # +8 > 5
        assert any("Accelerating" in p for p in signal_parts(latest, prev))

    def test_decelerating_rsi(self):
        prev   = make_row(close=100, sma8=100, sma21=90, sma55=80, rsi=60)
        latest = make_row(close=95,  sma8=99,  sma21=89, sma55=79, rsi=52)  # -8 < -5
        assert any("Decelerating" in p for p in signal_parts(latest, prev))

    def test_no_momentum_when_rsi_change_small(self):
        prev   = make_row(close=100, sma8=100, sma21=90, sma55=80, rsi=50)
        latest = make_row(close=103, sma8=101, sma21=91, sma55=81, rsi=53)  # +3, under threshold
        assert not any("Accelerating" in p or "Decelerating" in p for p in signal_parts(latest, prev))


class TestPriceCross:
    def test_price_crosses_above_55ma(self):
        prev   = make_row(close=78, sma8=100, sma21=90, sma55=80)
        latest = make_row(close=85, sma8=100, sma21=90, sma55=80)
        assert any("Price crossed ABOVE 55MA" in p for p in signal_parts(latest, prev))

    def test_price_crosses_below_55ma(self):
        prev   = make_row(close=85, sma8=100, sma21=90, sma55=80)
        latest = make_row(close=75, sma8=100, sma21=90, sma55=80)
        assert any("Price crossed BELOW 55MA" in p for p in signal_parts(latest, prev))


# ===========================================================================
# add_indicators
# ===========================================================================

def make_price_df(n, start=100.0, step=0.5):
    """Generate a synthetic OHLCV DataFrame with n rows."""
    closes  = [start + i * step for i in range(n)]
    volumes = [1000] * n
    return pd.DataFrame({
        "close":  closes,
        "open":   [c - 0.1 for c in closes],
        "high":   [c + 0.5 for c in closes],
        "low":    [c - 0.5 for c in closes],
        "volume": volumes,
    })


class TestAddIndicators:
    def test_returns_df_unchanged_when_too_few_rows(self):
        df = make_price_df(5)
        result = add_indicators(df)
        assert "sma8" not in result.columns

    def test_sma8_computed_with_sufficient_data(self):
        df = make_price_df(30)
        result = add_indicators(df)
        assert "sma8" in result.columns

    def test_sma21_fallback_for_small_df(self):
        """With <21 rows, sma21 uses a shorter fallback window."""
        df = make_price_df(15)
        result = add_indicators(df)
        assert "sma21" in result.columns

    def test_sma55_computed_with_full_data(self):
        df = make_price_df(60)
        result = add_indicators(df)
        assert "sma55" in result.columns
        assert result["sma55"].notna().any()

    def test_sma55_fallback_for_small_df(self):
        """With <55 rows, sma55 uses a shorter fallback window."""
        df = make_price_df(40)
        result = add_indicators(df)
        assert "sma55" in result.columns

    def test_rsi_computed(self):
        df = make_price_df(60)
        result = add_indicators(df)
        assert "rsi" in result.columns

    def test_rsi_fallback_for_small_df(self):
        df = make_price_df(12)
        result = add_indicators(df)
        assert "rsi" in result.columns

    def test_vol_avg_computed(self):
        df = make_price_df(60)
        result = add_indicators(df)
        assert "vol_avg" in result.columns

    def test_macd_computed(self):
        df = make_price_df(60)
        result = add_indicators(df)
        assert "macd" in result.columns
        assert "macd_histogram" in result.columns

    def test_macd_fallback_for_small_df(self):
        df = make_price_df(30)
        result = add_indicators(df)
        assert "macd" in result.columns


# ===========================================================================
# analyse_asset
# ===========================================================================

class TestAnalyseAsset:
    def _run(self, n_rows=100, prev_signals=None, is_crypto=False, symbol="BTC/GBP"):
        df = make_price_df(n_rows)
        prev_signals = prev_signals or {}
        new_signals, new_alerts = {}, []
        analyse_asset(symbol, df, is_crypto, prev_signals, new_signals, new_alerts)
        return new_signals, new_alerts

    def test_signal_stored_for_symbol(self):
        new_signals, _ = self._run()
        assert "BTC/GBP" in new_signals

    def test_alert_generated_when_signal_changes(self):
        new_signals, _ = self._run()
        # Second run with old signal — change the stored signal to force a diff
        _, alerts = self._run(prev_signals={"BTC/GBP": "something completely different"})
        assert len(alerts) == 1

    def test_alert_always_generated(self):
        """Every asset is always included in alerts regardless of signal change."""
        new_signals, _ = self._run()
        # Run again with the same signals — alert still generated
        _, alerts = self._run(prev_signals=new_signals)
        assert len(alerts) == 1

    def test_too_few_rows_produces_no_signal(self):
        new_signals, alerts = self._run(n_rows=3)
        assert "BTC/GBP" not in new_signals
        assert len(alerts) == 0

    def test_works_for_stock_symbol(self):
        new_signals, _ = self._run(symbol="AAPL", is_crypto=False)
        assert "AAPL" in new_signals

    def test_works_for_crypto_symbol(self):
        new_signals, _ = self._run(symbol="ETH/GBP", is_crypto=True)
        assert "ETH/GBP" in new_signals


# ===========================================================================
# format_output — additional missing lines
# ===========================================================================

class TestFormatOutputMissingLines:
    BASE_BULL = "📈 Bull Flag (Perfect Fibonacci Alignment) | 🔼 Daily UP | ✅ Price ABOVE SMA8 | ✅ Price ABOVE SMA21 | ✅ Price ABOVE SMA55"

    def _fmt(self, signal, close=100.0, prev_close=99.0, rsi=50.0):
        latest   = make_format_row(close, rsi)
        previous = make_format_row(prev_close, rsi)
        return format_output("TEST", latest, previous, signal, is_crypto=False)

    def test_default_mixed_flag_when_no_keyword_matches(self):
        """Line 102: else branch — signal has no Bull/Bear/Mixed keyword."""
        signal = "⚪️ Unknown | 🔼 Daily UP | ✅ Price ABOVE SMA8 | ✅ Price ABOVE SMA21 | ✅ Price ABOVE SMA55"
        result = self._fmt(signal)
        assert "⚪️ Mixed" in result

    def test_daily_up_change_in_key_changes(self):
        """Line 146: Daily UP (was: Daily DOWN) triggers 🔼 Daily UP key change."""
        signal = "📈 Bull Flag (Perfect Fibonacci Alignment) | 🔼 Daily UP (was: 🔽 Daily DOWN) | ✅ Price ABOVE SMA8 | ✅ Price ABOVE SMA21 | ✅ Price ABOVE SMA55"
        result = self._fmt(signal)
        assert "🔼 Daily UP" in result

    def test_daily_down_change_in_key_changes(self):
        """Line 148: Daily DOWN (was: Daily UP) triggers 🔽 Daily DOWN key change."""
        signal = "📈 Bull Flag (Perfect Fibonacci Alignment) | 🔽 Daily DOWN (was: 🔼 Daily UP) | ✅ Price ABOVE SMA8 | ✅ Price ABOVE SMA21 | ✅ Price ABOVE SMA55"
        result = self._fmt(signal)
        assert "🔽 Daily DOWN" in result

    def test_rsi_oversold_change(self):
        """Lines 154-155: RSI OVERSOLD key change."""
        signal = f"{self.BASE_BULL} | RSI OVERSOLD (was: normal)"
        result = self._fmt(signal, rsi=28.0)
        assert "RSI OVERSOLD" in result

    def test_rsi_overbought_change(self):
        """Lines 156-157: RSI OVERBOUGHT key change."""
        signal = f"{self.BASE_BULL} | RSI OVERBOUGHT (was: normal)"
        result = self._fmt(signal, rsi=72.0)
        assert "RSI OVERBOUGHT" in result

    def test_rsi_near_overbought_change(self):
        """Lines 158-159: RSI Near Overbought key change."""
        signal = f"{self.BASE_BULL} | RSI Near Overbought (was: normal)"
        result = self._fmt(signal, rsi=68.0)
        assert "RSI heating up" in result

    def test_rsi_near_oversold_change(self):
        """Lines 160-161: RSI Near Oversold key change."""
        signal = f"{self.BASE_BULL} | RSI Near Oversold (was: normal)"
        result = self._fmt(signal, rsi=32.0)
        assert "RSI cooling" in result


class TestAddIndicatorsErrorHandling:
    def test_exception_in_add_indicators_returns_df(self):
        """Lines 295-297: exception handler returns df without crashing."""
        import pandas as pd
        from unittest.mock import patch
        df = make_price_df(60)
        with patch("ta.trend.sma_indicator", side_effect=Exception("TA error")):
            result = add_indicators(df)
        assert isinstance(result, pd.DataFrame)


class TestAnalyseAssetMissingLines:
    def _run(self, n_rows=100, prev_signals=None, symbol="BTC/GBP", is_crypto=True):
        df = make_price_df(n_rows)
        prev_signals = prev_signals or {}
        new_signals, new_alerts = {}, []
        analyse_asset(symbol, df, is_crypto, prev_signals, new_signals, new_alerts)
        return new_signals, new_alerts

    def test_limited_data_still_produces_signal(self):
        """Line 306: < 55 rows logs warning but still works."""
        new_signals, _ = self._run(n_rows=40)
        assert "BTC/GBP" in new_signals

    def test_rsi_nan_produces_no_signal(self):
        """Lines 319-321: pd.isna(latest.rsi) triggers early return."""
        from unittest.mock import patch
        # Patch pd.isna inside technical_analysis to return True so the
        # NaN guard fires even though dropna already cleaned the column.
        with patch("technical_analysis.pd.isna", return_value=True):
            new_signals, alerts = self._run()
        assert "BTC/GBP" not in new_signals
        assert len(alerts) == 0

    def test_not_enough_rows_after_dropna(self):
        """Lines 312-313: fewer than 2 clean rows triggers early return."""
        import pandas as pd
        # Build a df with exactly 2 rows but NaN in essential cols so dropna
        # leaves only 1 row, hitting the len < 2 guard.
        df = pd.DataFrame({
            "close":  [100.0, float("nan")],
            "open":   [99.0,  99.0],
            "high":   [101.0, 101.0],
            "low":    [98.0,  98.0],
            "volume": [1000,  1000],
        })
        new_signals, alerts = {}, []
        analyse_asset("BAD", df, False, {}, new_signals, alerts)
        assert "BAD" not in new_signals


# ===========================================================================
# main.py — integration tests for the __main__ block (lines 34-69)
# ===========================================================================

class TestFinalMissingLines:
    def test_death_cross_key_change(self):
        """Line 152: Death Cross key change label."""
        signal = (
            "📈 Bull Flag (Perfect Fibonacci Alignment) | 🔼 Daily UP"
            " | ✅ Price ABOVE SMA8 | ✅ Price ABOVE SMA21 | ✅ Price ABOVE SMA55"
            " | ⚠️ Death Cross (SMA8 ↓ SMA55) (was: ⚠️ No Cross)"
        )
        latest   = make_format_row(100.0, rsi=50.0)
        previous = make_format_row(99.0,  rsi=50.0)
        result = format_output("TEST", latest, previous, signal, is_crypto=False)
        assert "Death Cross" in result

    def test_rsi_nan_early_return_in_analyse_asset(self):
        """Lines 320-321: pd.isna(latest.rsi) triggers early return."""
        from unittest.mock import patch
        new_signals, alerts = {}, []
        with patch("technical_analysis.pd.isna", return_value=True):
            analyse_asset("SYM", make_price_df(60), False, {}, new_signals, alerts)
        assert "SYM" not in new_signals
        assert len(alerts) == 0