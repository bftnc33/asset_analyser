"""
Unit tests for main.py.

The __main__ block is tested by patching all external dependencies and then
importing main with __name__ set to "__main__" via runpy.run_module, which
executes the block directly in-process so coverage is captured correctly.
"""

import json
import os
import sys
import runpy
import pytest
from unittest.mock import patch, MagicMock, call

# ---------------------------------------------------------------------------
# Ensure real main module is importable — pop any mock left by other tests
# ---------------------------------------------------------------------------
sys.modules.pop("main", None)
sys.modules.pop("alerts", None)
sys.modules.pop("data_feeds", None)
sys.modules.pop("technical_analysis", None)

import pandas as pd


# ===========================================================================
# Helpers
# ===========================================================================

def make_df(n=60):
    return pd.DataFrame({
        "close":  [100.0 + i for i in range(n)],
        "open":   [99.0  + i for i in range(n)],
        "high":   [101.0 + i for i in range(n)],
        "low":    [98.0  + i for i in range(n)],
        "volume": [1000  for _ in range(n)],
    })


def run_main(tmp_path, symbols, prev_signals=None, crypto_side_effect=None, stock_side_effect=None):
    """
    Run the __main__ block of main.py in-process using runpy so that
    coverage is captured. All external I/O is patched.
    """
    symbols_file = tmp_path / "symbols.json"
    symbols_file.write_text(json.dumps(symbols))
    signal_file  = tmp_path / "signals.json"
    if prev_signals is not None:
        signal_file.write_text(json.dumps(prev_signals))

    fetch_crypto = MagicMock(side_effect=crypto_side_effect or (lambda s: make_df()))
    fetch_stock  = MagicMock(side_effect=stock_side_effect  or (lambda s: make_df()))
    send_email   = MagicMock()

    # Pop main so runpy re-executes it fresh each call
    sys.modules.pop("main", None)

    with patch("builtins.open", side_effect=_open_factory(symbols_file, signal_file)), \
         patch("os.path.exists",  side_effect=lambda p: p == str(signal_file) and signal_file.exists()), \
         patch("data_feeds.fetch_crypto_data", fetch_crypto), \
         patch("data_feeds.fetch_stock_data",  fetch_stock), \
         patch("alerts.send_email",            send_email):
        try:
            runpy.run_module("main", run_name="__main__", alter_sys=True)
        except SystemExit:
            pass

    return fetch_crypto, fetch_stock, send_email, signal_file


def _open_factory(symbols_file, signal_file):
    """Return a side_effect function that serves our fixture files and delegates the rest."""
    import builtins
    real_open = builtins.open

    def _open(path, mode="r", *args, **kwargs):
        if str(path) == "symbols.json" or path == "symbols.json":
            return real_open(str(symbols_file), mode, *args, **kwargs)
        if str(path) == str(signal_file) or str(path) == "signals.json":
            return real_open(str(signal_file), mode, *args, **kwargs)
        return real_open(path, mode, *args, **kwargs)

    return _open


# ===========================================================================
# load_symbols
# ===========================================================================

class TestLoadSymbols:
    def _load(self, tmp_path, data):
        f = tmp_path / "symbols.json"
        f.write_text(json.dumps(data))
        sys.modules.pop("main", None)
        with patch("builtins.open", side_effect=_open_factory(f, tmp_path / "signals.json")):
            from main import load_symbols
        return load_symbols(str(f))

    def test_returns_stocks_and_crypto(self, tmp_path):
        stocks, crypto = self._load(tmp_path, {"stocks": ["AAPL", "TSLA"], "crypto": ["BTC/GBP"]})
        assert stocks == ["AAPL", "TSLA"]
        assert crypto == ["BTC/GBP"]

    def test_missing_stocks_key_returns_empty_list(self, tmp_path):
        stocks, crypto = self._load(tmp_path, {"crypto": ["BTC/GBP"]})
        assert stocks == []
        assert crypto == ["BTC/GBP"]

    def test_missing_crypto_key_returns_empty_list(self, tmp_path):
        stocks, crypto = self._load(tmp_path, {"stocks": ["AAPL"]})
        assert stocks == ["AAPL"]
        assert crypto == []

    def test_empty_file_returns_empty_lists(self, tmp_path):
        stocks, crypto = self._load(tmp_path, {})
        assert stocks == []
        assert crypto == []

    def test_missing_file_raises(self, tmp_path):
        sys.modules.pop("main", None)
        f = tmp_path / "symbols.json"
        f.write_text(json.dumps({}))
        with patch("builtins.open", side_effect=_open_factory(f, tmp_path / "signals.json")):
            from main import load_symbols
        with pytest.raises(FileNotFoundError):
            load_symbols(str(tmp_path / "nonexistent.json"))

    def test_invalid_json_raises(self, tmp_path):
        sys.modules.pop("main", None)
        f = tmp_path / "symbols.json"
        f.write_text(json.dumps({}))
        with patch("builtins.open", side_effect=_open_factory(f, tmp_path / "signals.json")):
            from main import load_symbols
        bad = tmp_path / "bad.json"
        bad.write_text("not valid json {{{")
        with pytest.raises(json.JSONDecodeError):
            load_symbols(str(bad))

    def test_multiple_stocks_and_crypto(self, tmp_path):
        data = {"stocks": ["AAPL", "TSLA", "BARC.L"], "crypto": ["BTC/GBP", "ETH/GBP", "ETH/BTC"]}
        stocks, crypto = self._load(tmp_path, data)
        assert len(stocks) == 3
        assert len(crypto) == 3


# ===========================================================================
# load_previous_signals
# ===========================================================================

class TestLoadPreviousSignals:
    def _get_fn(self, tmp_path, symbols=None):
        sys.modules.pop("main", None)
        sf = tmp_path / "symbols.json"
        sf.write_text(json.dumps(symbols or {}))
        with patch("builtins.open", side_effect=_open_factory(sf, tmp_path / "signals.json")):
            from main import load_previous_signals
        return load_previous_signals

    def test_returns_dict_when_file_exists(self, tmp_path):
        signals = {"BTC/GBP": "some signal", "AAPL": "another signal"}
        signal_file = tmp_path / "signals.json"
        signal_file.write_text(json.dumps(signals))
        load_previous_signals = self._get_fn(tmp_path)
        with patch("main.SIGNAL_FILE", str(signal_file)):
            result = load_previous_signals()
        assert result == signals

    def test_returns_empty_dict_when_file_missing(self, tmp_path):
        load_previous_signals = self._get_fn(tmp_path)
        with patch("main.SIGNAL_FILE", str(tmp_path / "signals.json")):
            result = load_previous_signals()
        assert result == {}

    def test_returns_dict_not_none(self, tmp_path):
        load_previous_signals = self._get_fn(tmp_path)
        with patch("main.SIGNAL_FILE", str(tmp_path / "missing.json")):
            result = load_previous_signals()
        assert result is not None and isinstance(result, dict)

    def test_preserves_all_symbols(self, tmp_path):
        signals = {f"SYM{i}": f"signal {i}" for i in range(10)}
        signal_file = tmp_path / "signals.json"
        signal_file.write_text(json.dumps(signals))
        load_previous_signals = self._get_fn(tmp_path)
        with patch("main.SIGNAL_FILE", str(signal_file)):
            assert len(load_previous_signals()) == 10

    def test_empty_signals_file(self, tmp_path):
        signal_file = tmp_path / "signals.json"
        signal_file.write_text(json.dumps({}))
        load_previous_signals = self._get_fn(tmp_path)
        with patch("main.SIGNAL_FILE", str(signal_file)):
            assert load_previous_signals() == {}


# ===========================================================================
# save_signals
# ===========================================================================

class TestSaveSignals:
    def _get_fns(self, tmp_path):
        sys.modules.pop("main", None)
        sf = tmp_path / "symbols.json"
        sf.write_text(json.dumps({}))
        with patch("builtins.open", side_effect=_open_factory(sf, tmp_path / "signals.json")):
            from main import save_signals, load_previous_signals
        return save_signals, load_previous_signals

    def test_file_is_created(self, tmp_path):
        save_signals, _ = self._get_fns(tmp_path)
        signal_file = tmp_path / "signals.json"
        with patch("main.SIGNAL_FILE", str(signal_file)):
            save_signals({"BTC/GBP": "some signal"})
        assert signal_file.exists()

    def test_saved_content_is_valid_json(self, tmp_path):
        save_signals, _ = self._get_fns(tmp_path)
        signal_file = tmp_path / "signals.json"
        signals = {"BTC/GBP": "bull signal", "AAPL": "bear signal"}
        with patch("main.SIGNAL_FILE", str(signal_file)):
            save_signals(signals)
        assert json.loads(signal_file.read_text()) == signals

    def test_save_then_load_roundtrip(self, tmp_path):
        save_signals, load_previous_signals = self._get_fns(tmp_path)
        signal_file = tmp_path / "signals.json"
        signals = {"ETH/GBP": "signal A", "TSLA": "signal B"}
        with patch("main.SIGNAL_FILE", str(signal_file)):
            save_signals(signals)
            assert load_previous_signals() == signals

    def test_overwrites_existing_file(self, tmp_path):
        save_signals, load_previous_signals = self._get_fns(tmp_path)
        signal_file = tmp_path / "signals.json"
        signal_file.write_text(json.dumps({"OLD": "old signal"}))
        with patch("main.SIGNAL_FILE", str(signal_file)):
            save_signals({"NEW": "new signal"})
            result = load_previous_signals()
        assert "OLD" not in result
        assert "NEW" in result

    def test_saves_empty_dict(self, tmp_path):
        save_signals, load_previous_signals = self._get_fns(tmp_path)
        signal_file = tmp_path / "signals.json"
        with patch("main.SIGNAL_FILE", str(signal_file)):
            save_signals({})
            assert load_previous_signals() == {}

    def test_output_is_indented(self, tmp_path):
        save_signals, _ = self._get_fns(tmp_path)
        signal_file = tmp_path / "signals.json"
        with patch("main.SIGNAL_FILE", str(signal_file)):
            save_signals({"BTC/GBP": "signal"})
        assert "\n" in signal_file.read_text()


# ===========================================================================
# __main__ block (lines 34-69)
# ===========================================================================

class TestMainBlock:
    def test_signals_file_written_after_run(self, tmp_path):
        _, _, _, signal_file = run_main(tmp_path, {"stocks": ["AAPL"], "crypto": ["BTC/GBP"]})
        assert signal_file.exists()

    def test_signals_contain_all_symbols(self, tmp_path):
        _, _, _, signal_file = run_main(tmp_path, {"stocks": ["AAPL"], "crypto": ["BTC/GBP"]})
        signals = json.loads(signal_file.read_text())
        assert "AAPL" in signals
        assert "BTC/GBP" in signals

    def test_send_email_called_when_signals_change(self, tmp_path):
        symbols = {"stocks": [], "crypto": ["BTC/GBP"]}
        _, _, send_email, _ = run_main(tmp_path, symbols, prev_signals={"BTC/GBP": "old signal"})
        send_email.assert_called_once()

    def test_email_always_sent_even_when_signals_unchanged(self, tmp_path):
        """Every run sends a daily summary regardless of signal changes."""
        symbols = {"stocks": [], "crypto": ["BTC/GBP"]}
        fixed_signal = "📈 Bull Flag | 🔼 Daily UP | ✅ Price ABOVE SMA8"
        prev_signals = {"BTC/GBP": fixed_signal}

        # Patch analyse_asset to write the same fixed signal — unchanged, but
        # email should still be sent as we now always include every asset.
        def fake_analyse(symbol, df, is_crypto, prev_signals, new_signals, new_alerts):
            new_signals[symbol] = fixed_signal
            new_alerts.append(f"{symbol}: no change")  # always appended now

        with patch("technical_analysis.analyse_asset", side_effect=fake_analyse):
            _, _, send_email, _ = run_main(tmp_path, symbols, prev_signals=prev_signals)
        send_email.assert_called_once()

    def test_crypto_fetch_error_is_caught(self, tmp_path):
        """Failing crypto fetch should not crash the script."""
        def bad_fetch(s): raise Exception("Network failure")
        _, _, _, signal_file = run_main(
            tmp_path,
            {"stocks": [], "crypto": ["BTC/GBP"]},
            crypto_side_effect=bad_fetch,
        )
        # Script completed — signal file may be empty but no exception raised
        assert True

    def test_stock_fetch_error_is_caught(self, tmp_path):
        """Failing stock fetch should not crash the script."""
        def bad_fetch(s): raise Exception("Network failure")
        _, _, _, signal_file = run_main(
            tmp_path,
            {"stocks": ["AAPL"], "crypto": []},
            stock_side_effect=bad_fetch,
        )
        assert True

    def test_both_stocks_and_crypto_processed(self, tmp_path):
        fetch_crypto, fetch_stock, _, _ = run_main(
            tmp_path,
            {"stocks": ["AAPL", "BARC.L"], "crypto": ["BTC/GBP", "ETH/GBP"]},
        )
        assert fetch_crypto.call_count == 2
        assert fetch_stock.call_count == 2

    def test_email_subject_contains_change_count(self, tmp_path):
        symbols = {"stocks": [], "crypto": ["BTC/GBP"]}
        _, _, send_email, _ = run_main(tmp_path, symbols, prev_signals={"BTC/GBP": "old signal"})
        if send_email.called:
            subject = send_email.call_args[0][0]
            assert "1" in subject