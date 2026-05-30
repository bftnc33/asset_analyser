"""
Unit tests for the crossover detection logic in generate_signal().

Each test constructs minimal `latest` and `prev` row stubs using SimpleNamespace
so that no real price data or DataFrame is needed.  The `df` argument is only
used by get_volume_color(); a two-row stub DataFrame is sufficient.
"""

import pandas as pd
import pytest
from types import SimpleNamespace
from technical_analysis import generate_signal


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_row(close, sma8, sma21, sma55, rsi=50.0, volume=1000, vol_avg=1000):
    """Return a SimpleNamespace that looks like a DataFrame row to generate_signal."""
    return SimpleNamespace(
        close=close, sma8=sma8, sma21=sma21, sma55=sma55,
        rsi=rsi, volume=volume, vol_avg=vol_avg,
    )


def make_df(prev_close, latest_close):
    """Two-row DataFrame used only for volume colour detection."""
    return pd.DataFrame({"close": [prev_close, latest_close], "volume": [1000, 1000]})


def signal_parts(latest, prev):
    """Return the signal as a set of pipe-separated parts for easy assertion."""
    df = make_df(prev.close, latest.close)
    raw = generate_signal(df, latest, prev)
    return set(part.strip() for part in raw.split("|"))


# ---------------------------------------------------------------------------
# Flag (overall alignment) tests
# ---------------------------------------------------------------------------

class TestFlag:
    def test_bull_flag_when_8_gt_21_gt_55(self):
        latest = make_row(close=110, sma8=100, sma21=90, sma55=80)
        prev   = make_row(close=109, sma8=99,  sma21=91, sma55=81)
        parts  = signal_parts(latest, prev)
        assert any("Bull Flag" in p for p in parts)

    def test_bear_flag_when_8_lt_21_lt_55(self):
        latest = make_row(close=70, sma8=80, sma21=90, sma55=100)
        prev   = make_row(close=71, sma8=81, sma21=91, sma55=101)
        parts  = signal_parts(latest, prev)
        assert any("Bear Flag" in p for p in parts)

    def test_mixed_signals_when_not_aligned(self):
        latest = make_row(close=90, sma8=85, sma21=80, sma55=95)
        prev   = make_row(close=91, sma8=84, sma21=81, sma55=96)
        parts  = signal_parts(latest, prev)
        assert any("Mixed Signals" in p for p in parts)


# ---------------------------------------------------------------------------
# Crossover tests
# ---------------------------------------------------------------------------

class TestCrossovers:
    def test_golden_cross(self):
        """sma8 crosses above sma55 — bullish signal."""
        prev   = make_row(close=100, sma8=78, sma21=85, sma55=80)   # sma8 <= sma55
        latest = make_row(close=110, sma8=83, sma21=85, sma55=80)   # sma8 now > sma55
        parts  = signal_parts(latest, prev)
        assert any("Golden Cross" in p for p in parts)

    def test_death_cross(self):
        """sma8 crosses below sma55 — bearish signal."""
        prev   = make_row(close=100, sma8=82, sma21=85, sma55=80)   # sma8 >= sma55
        latest = make_row(close=80,  sma8=77, sma21=85, sma55=80)   # sma8 now < sma55
        parts  = signal_parts(latest, prev)
        assert any("Death Cross" in p for p in parts)

    def test_no_crossover_sma21_crosses_sma55(self):
        """sma21 crossing sma55 alone does NOT produce a crossover signal."""
        prev   = make_row(close=100, sma8=100, sma21=78, sma55=80)  # sma21 < sma55, sma8 stable above both
        latest = make_row(close=110, sma8=100, sma21=82, sma55=80)  # sma21 now > sma55, sma8 unchanged
        parts  = signal_parts(latest, prev)
        assert not any("Cross" in p for p in parts)

    def test_no_crossover_when_stable(self):
        """No crossover emitted when sma8 stays on same side of sma55."""
        prev   = make_row(close=100, sma8=100, sma21=90, sma55=80)
        latest = make_row(close=105, sma8=101, sma21=91, sma55=81)
        parts  = signal_parts(latest, prev)
        assert not any("Cross" in p for p in parts)


# ---------------------------------------------------------------------------
# Price-vs-SMA crossover tests
# ---------------------------------------------------------------------------

class TestPriceCross:
    def test_price_crosses_above_55ma(self):
        prev   = make_row(close=78, sma8=100, sma21=90, sma55=80)   # close <= sma55
        latest = make_row(close=85, sma8=100, sma21=90, sma55=80)   # close now > sma55
        parts  = signal_parts(latest, prev)
        assert any("Price crossed ABOVE 55MA" in p for p in parts)

    def test_price_crosses_below_55ma(self):
        prev   = make_row(close=85, sma8=100, sma21=90, sma55=80)   # close >= sma55
        latest = make_row(close=75, sma8=100, sma21=90, sma55=80)   # close now < sma55
        parts  = signal_parts(latest, prev)
        assert any("Price crossed BELOW 55MA" in p for p in parts)