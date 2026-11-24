"""
Tests for technical_analysis.py.

Covers: diff_signal_parts, format_output, get_volume_color,
        generate_signal (bull/bear flag, SMA200 distance, volume,
        RSI momentum), add_indicators, and analyse_asset.
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

def make_row(close, sma200, rsi=50.0, volume=1000, vol_avg=1000):
    return SimpleNamespace(
        close=close, sma200=sma200,
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
        signal = "📈 Bull Flag (Price ABOVE SMA200) | 🔼 Weekly UP | ✅ Price ABOVE SMA200"
        result = diff_signal_parts(signal, signal)
        assert "(was:" not in result

    def test_flag_change_annotated(self):
        old = "📈 Bull Flag (Price ABOVE SMA200) | 🔼 Weekly UP"
        new = "📉 Bear Flag (Price BELOW SMA200) | 🔼 Weekly UP"
        result = diff_signal_parts(old, new)
        assert "(was:" in result
        assert "Bear Flag" in result

    def test_sma200_position_change_annotated(self):
        old = "📈 Bull Flag | 🔻 Price BELOW SMA200"
        new = "📈 Bull Flag | ✅ Price ABOVE SMA200"
        result = diff_signal_parts(old, new)
        assert "(was:" in result
        assert "ABOVE SMA200" in result

    def test_sma200_distance_change_annotated(self):
        old = "📈 Bull Flag | SMA200 Distance: +5.0%"
        new = "📈 Bull Flag | SMA200 Distance: +10.0%"
        result = diff_signal_parts(old, new)
        assert "(was:" in result

    def test_weekly_trend_change_annotated(self):
        old = "📈 Bull Flag | 🔼 Weekly UP"
        new = "📈 Bull Flag | 🔽 Weekly DOWN"
        result = diff_signal_parts(old, new)
        assert "(was:" in result

    def test_strips_existing_changes_section_from_old(self):
        old = "📈 Bull Flag | 🔼 Weekly UP ↪️ Changes: something"
        new = "📈 Bull Flag | 🔽 Weekly DOWN"
        result = diff_signal_parts(old, new)
        assert "↪️ Changes:" not in result


# ===========================================================================
# format_output — currency / price formatting
# ===========================================================================

class TestFormatOutputCurrency:
    BASE_SIGNAL = (
        "📈 Bull Flag (Price ABOVE SMA200) | 🔼 Weekly UP "
        "| ✅ Price ABOVE SMA200 | SMA200 Distance: +5.0%"
    )

    def _fmt(self, symbol, close, prev_close=None,
             is_crypto=False, rsi=50.0):
        if prev_close is None:
            prev_close = close * 0.99
        latest   = make_format_row(close, rsi)
        previous = make_format_row(prev_close, rsi)
        return format_output(
            symbol, latest, previous, self.BASE_SIGNAL, is_crypto
        )

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
        result = self._fmt("SGLN.L", 2750, 2700, is_crypto=False)
        assert "£" in result
        assert "27" in result  # 2750p → ~£27.50

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
        return format_output(
            "TEST", latest, previous, signal, is_crypto=False
        )

    def test_bull_flag_shown(self):
        sig = (
            "📈 Bull Flag (Price ABOVE SMA200) | 🔼 Weekly UP "
            "| ✅ Price ABOVE SMA200 | SMA200 Distance: +5.0%"
        )
        assert "📈 Bull" in self._fmt(sig)

    def test_bear_flag_shown(self):
        sig = (
            "📉 Bear Flag (Price BELOW SMA200) | 🔽 Weekly DOWN "
            "| 🔻 Price BELOW SMA200 | SMA200 Distance: -8.0%"
        )
        assert "📉 Bear" in self._fmt(sig)

    def test_sma200_distance_shown_in_output(self):
        sig = (
            "📈 Bull Flag (Price ABOVE SMA200) | 🔼 Weekly UP "
            "| ✅ Price ABOVE SMA200 | SMA200 Distance: +12.3%"
        )
        assert "SMA200 Distance: +12.3%" in self._fmt(sig)

    def test_rsi_accelerating_arrow(self):
        sig = (
            "📈 Bull Flag (Price ABOVE SMA200) | 🔼 Weekly UP "
            "| ✅ Price ABOVE SMA200 | SMA200 Distance: +5.0% "
            "| RSI ↗️ Accelerating"
        )
        assert "↗️" in self._fmt(sig)

    def test_rsi_decelerating_arrow(self):
        sig = (
            "📈 Bull Flag (Price ABOVE SMA200) | 🔼 Weekly UP "
            "| ✅ Price ABOVE SMA200 | SMA200 Distance: +5.0% "
            "| RSI ↘️ Decelerating"
        )
        assert "↘️" in self._fmt(sig)


class TestFormatOutputKeyChanges:
    def _fmt_with_change(self, changed_part):
        signal = (
            f"📈 Bull Flag (Price ABOVE SMA200) | 🔼 Weekly UP "
            f"| {changed_part} | SMA200 Distance: +5.0%"
        )
        latest   = make_format_row(100.0, rsi=50.0)
        previous = make_format_row(99.0,  rsi=50.0)
        return format_output(
            "TEST", latest, previous, signal, is_crypto=False
        )

    def test_broke_above_sma200(self):
        result = self._fmt_with_change(
            "✅ Price ABOVE SMA200 (was: 🔻 Price BELOW SMA200)"
        )
        assert "Broke ABOVE SMA200" in result

    def test_broke_below_sma200(self):
        result = self._fmt_with_change(
            "🔻 Price BELOW SMA200 (was: ✅ Price ABOVE SMA200)"
        )
        assert "Broke BELOW SMA200" in result

    def test_turned_bullish(self):
        signal = (
            "📈 Bull Flag (Price ABOVE SMA200) (was: 📉 Bear Flag) "
            "| 🔼 Weekly UP | ✅ Price ABOVE SMA200 | SMA200 Distance: +5.0%"
        )
        latest   = make_format_row(100.0)
        previous = make_format_row(99.0)
        result = format_output(
            "TEST", latest, previous, signal, is_crypto=False
        )
        assert "Turned BULLISH" in result

    def test_turned_bearish(self):
        signal = (
            "📉 Bear Flag (Price BELOW SMA200) (was: 📈 Bull Flag) "
            "| 🔽 Weekly DOWN | 🔻 Price BELOW SMA200 | SMA200 Distance: -5.0%"
        )
        latest   = make_format_row(100.0)
        previous = make_format_row(101.0)
        result = format_output(
            "TEST", latest, previous, signal, is_crypto=False
        )
        assert "Turned BEARISH" in result

    def test_weekly_up_change(self):
        signal = (
            "📈 Bull Flag (Price ABOVE SMA200) "
            "| 🔼 Weekly UP (was: 🔽 Weekly DOWN) "
            "| ✅ Price ABOVE SMA200 | SMA200 Distance: +5.0%"
        )
        latest   = make_format_row(100.0)
        previous = make_format_row(99.0)
        result = format_output(
            "TEST", latest, previous, signal, is_crypto=False
        )
        assert "🔼 Weekly UP" in result

    def test_weekly_down_change(self):
        signal = (
            "📈 Bull Flag (Price ABOVE SMA200) "
            "| 🔽 Weekly DOWN (was: 🔼 Weekly UP) "
            "| ✅ Price ABOVE SMA200 | SMA200 Distance: +5.0%"
        )
        latest   = make_format_row(100.0)
        previous = make_format_row(101.0)
        result = format_output(
            "TEST", latest, previous, signal, is_crypto=False
        )
        assert "🔽 Weekly DOWN" in result

    def test_no_changes_line_when_signal_unchanged(self):
        signal = (
            "📈 Bull Flag (Price ABOVE SMA200) | 🔼 Weekly UP "
            "| ✅ Price ABOVE SMA200 | SMA200 Distance: +5.0%"
        )
        latest   = make_format_row(100.0)
        previous = make_format_row(99.0)
        result = format_output(
            "TEST", latest, previous, signal, is_crypto=False
        )
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
# generate_signal — bull/bear, SMA200 distance, volume, RSI momentum
# ===========================================================================

class TestFlag:
    def test_bull_flag_when_price_above_sma200(self):
        latest = make_row(close=110, sma200=100)
        prev   = make_row(close=109, sma200=100)
        assert any("Bull Flag" in p for p in signal_parts(latest, prev))

    def test_bear_flag_when_price_below_sma200(self):
        latest = make_row(close=90, sma200=100)
        prev   = make_row(close=91, sma200=100)
        assert any("Bear Flag" in p for p in signal_parts(latest, prev))

    def test_price_above_sma200_part_present(self):
        latest = make_row(close=110, sma200=100)
        prev   = make_row(close=109, sma200=100)
        assert any("ABOVE SMA200" in p for p in signal_parts(latest, prev))

    def test_price_below_sma200_part_present(self):
        latest = make_row(close=90, sma200=100)
        prev   = make_row(close=91, sma200=100)
        assert any("BELOW SMA200" in p for p in signal_parts(latest, prev))


class TestSMA200Distance:
    def test_positive_distance_when_above(self):
        latest = make_row(close=110, sma200=100)
        prev   = make_row(close=109, sma200=100)
        parts  = signal_parts(latest, prev)
        assert any("Distance: +10.0%" in p for p in parts)

    def test_negative_distance_when_below(self):
        latest = make_row(close=90, sma200=100)
        prev   = make_row(close=91, sma200=100)
        parts  = signal_parts(latest, prev)
        assert any("Distance: -10.0%" in p for p in parts)

    def test_zero_distance_at_sma200(self):
        latest = make_row(close=100, sma200=100)
        prev   = make_row(close=99,  sma200=100)
        parts  = signal_parts(latest, prev)
        assert any("Distance: +0.0%" in p for p in parts)


class TestVolume:
    def _parts_with_volume(self, volume, vol_avg):
        prev   = make_row(close=100, sma200=90, volume=vol_avg,  vol_avg=vol_avg)
        latest = make_row(close=105, sma200=90, volume=volume, vol_avg=vol_avg)
        return signal_parts(latest, prev)

    def test_major_buying_volume(self):
        parts = self._parts_with_volume(volume=3000, vol_avg=1000)
        assert any("MAJOR BUYING" in p for p in parts)

    def test_major_selling_volume(self):
        prev   = make_row(close=105, sma200=90, volume=1000, vol_avg=1000)
        latest = make_row(close=100, sma200=90, volume=3000, vol_avg=1000)
        parts  = signal_parts(latest, prev)
        assert any("MAJOR SELLING" in p for p in parts)

    def test_strong_buying_volume(self):
        parts = self._parts_with_volume(volume=2000, vol_avg=1000)
        assert any("Strong Buying" in p for p in parts)

    def test_strong_selling_volume(self):
        prev   = make_row(close=105, sma200=90, volume=1000, vol_avg=1000)
        latest = make_row(close=100, sma200=90, volume=2000, vol_avg=1000)
        parts  = signal_parts(latest, prev)
        assert any("Strong Selling" in p for p in parts)

    def test_normal_volume_no_spike(self):
        parts = self._parts_with_volume(volume=1100, vol_avg=1000)
        assert not any("Volume" in p for p in parts)

    def test_zero_vol_avg_no_crash(self):
        prev   = make_row(close=100, sma200=90, volume=1000, vol_avg=0)
        latest = make_row(close=105, sma200=90, volume=1000, vol_avg=0)
        parts  = signal_parts(latest, prev)
        assert isinstance(parts, set)


class TestRSIMomentum:
    def test_accelerating_rsi(self):
        prev   = make_row(close=100, sma200=90, rsi=40)
        latest = make_row(close=105, sma200=90, rsi=48)
        assert any("Accelerating" in p for p in signal_parts(latest, prev))

    def test_decelerating_rsi(self):
        prev   = make_row(close=100, sma200=90, rsi=60)
        latest = make_row(close=95,  sma200=90, rsi=52)
        assert any("Decelerating" in p for p in signal_parts(latest, prev))

    def test_no_momentum_when_rsi_change_small(self):
        prev   = make_row(close=100, sma200=90, rsi=50)
        latest = make_row(close=103, sma200=90, rsi=53)
        assert not any(
            "Accelerating" in p or "Decelerating" in p
            for p in signal_parts(latest, prev)
        )


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
        df = make_price_df(50)
        result = add_indicators(df)
        assert "sma200" not in result.columns

    def test_sma200_computed_with_sufficient_data(self):
        df = make_price_df(210)
        result = add_indicators(df)
        assert "sma200" in result.columns

    def test_rsi_computed(self):
        df = make_price_df(210)
        result = add_indicators(df)
        assert "rsi" in result.columns

    def test_vol_avg_computed(self):
        df = make_price_df(210)
        result = add_indicators(df)
        assert "vol_avg" in result.columns

    def test_no_sma8_column(self):
        df = make_price_df(210)
        result = add_indicators(df)
        assert "sma8" not in result.columns

    def test_no_sma21_column(self):
        df = make_price_df(210)
        result = add_indicators(df)
        assert "sma21" not in result.columns

    def test_no_sma55_column(self):
        df = make_price_df(210)
        result = add_indicators(df)
        assert "sma55" not in result.columns

    def test_no_macd_column(self):
        df = make_price_df(210)
        result = add_indicators(df)
        assert "macd" not in result.columns

    def test_sma200_values_are_numeric(self):
        df = make_price_df(210)
        result = add_indicators(df)
        assert pd.api.types.is_float_dtype(result["sma200"])


class TestAddIndicatorsErrorHandling:
    def test_exception_in_add_indicators_returns_df(self):
        df = make_price_df(210)
        with patch("ta.trend.sma_indicator", side_effect=Exception("TA error")):
            result = add_indicators(df)
        assert isinstance(result, pd.DataFrame)


# ===========================================================================
# analyse_asset
# ===========================================================================

class TestAnalyseAsset:
    def _run(self, n_rows=210, prev_signals=None,
             is_crypto=False, symbol="BTC/GBP"):
        df = make_price_df(n_rows)
        prev_signals = prev_signals or {}
        new_signals, new_alerts = {}, []
        analyse_asset(
            symbol, df, is_crypto, prev_signals, new_signals, new_alerts
        )
        return new_signals, new_alerts

    def test_signal_stored_for_symbol(self):
        new_signals, _ = self._run()
        assert "BTC/GBP" in new_signals

    def test_alert_generated(self):
        _, alerts = self._run()
        assert len(alerts) == 1

    def test_alert_always_generated_when_signal_unchanged(self):
        new_signals, _ = self._run()
        _, alerts = self._run(prev_signals=new_signals)
        assert len(alerts) == 1

    def test_too_few_rows_produces_no_signal(self):
        new_signals, alerts = self._run(n_rows=50)
        assert "BTC/GBP" not in new_signals
        assert len(alerts) == 0

    def test_works_for_stock_symbol(self):
        new_signals, _ = self._run(symbol="AAPL", is_crypto=False)
        assert "AAPL" in new_signals

    def test_works_for_crypto_symbol(self):
        new_signals, _ = self._run(symbol="ETH/GBP", is_crypto=True)
        assert "ETH/GBP" in new_signals


class TestAnalyseAssetMissingLines:
    def _run(self, n_rows=210, prev_signals=None,
             symbol="BTC/GBP", is_crypto=True):
        df = make_price_df(n_rows)
        prev_signals = prev_signals or {}
        new_signals, new_alerts = {}, []
        analyse_asset(
            symbol, df, is_crypto, prev_signals, new_signals, new_alerts
        )
        return new_signals, new_alerts

    def test_rsi_nan_produces_no_signal(self):
        with patch("technical_analysis.pd.isna", return_value=True):
            new_signals, alerts = self._run()
        assert "BTC/GBP" not in new_signals
        assert len(alerts) == 0

    def test_not_enough_rows_after_dropna(self):
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
# format_output — RSI key changes
# ===========================================================================

class TestFormatOutputRSIChanges:
    BASE_BULL = (
        "📈 Bull Flag (Price ABOVE SMA200) | 🔼 Weekly UP "
        "| ✅ Price ABOVE SMA200 | SMA200 Distance: +5.0%"
    )

    def _fmt(self, signal, close=100.0, prev_close=99.0, rsi=50.0):
        latest   = make_format_row(close, rsi)
        previous = make_format_row(prev_close, rsi)
        return format_output(
            "TEST", latest, previous, signal, is_crypto=False
        )

    def test_rsi_oversold_change(self):
        signal = f"{self.BASE_BULL} | RSI OVERSOLD (was: normal)"
        result = self._fmt(signal, rsi=28.0)
        assert "RSI OVERSOLD" in result

    def test_rsi_overbought_change(self):
        signal = f"{self.BASE_BULL} | RSI OVERBOUGHT (was: normal)"
        result = self._fmt(signal, rsi=72.0)
        assert "RSI OVERBOUGHT" in result

    def test_rsi_near_overbought_change(self):
        signal = f"{self.BASE_BULL} | RSI Near Overbought (was: normal)"
        result = self._fmt(signal, rsi=68.0)
        assert "RSI heating up" in result

    def test_rsi_near_oversold_change(self):
        signal = f"{self.BASE_BULL} | RSI Near Oversold (was: normal)"
        result = self._fmt(signal, rsi=32.0)
        assert "RSI cooling" in result