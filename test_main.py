"""
Unit tests for main.py.

The main loop runs at module level under `if __name__ == "__main__"` so it
cannot be imported and re-executed in tests. Instead we test the three
testable functions directly:

    load_symbols          — reads symbols.json and returns (stocks, crypto)
    load_previous_signals — reads signals.json or returns {} if absent
    save_signals          — writes signals.json to disk

All external dependencies (alerts, data_feeds, technical_analysis) are patched
at import time so the module loads cleanly without needing live credentials or
network access. All file I/O is performed against pytest's tmp_path fixture so
no production files are touched.
"""

import json
import sys
import pytest
from unittest.mock import patch, mock_open, MagicMock

# ---------------------------------------------------------------------------
# Patch external modules before importing main, so the module-level
# load_symbols() call and all imports succeed without side effects.
# ---------------------------------------------------------------------------
SYMBOLS_FIXTURE = {"stocks": ["AAPL", "BARC.L"], "crypto": ["BTC/GBP", "ETH/GBP"]}

_alerts_mock        = MagicMock()
_data_feeds_mock    = MagicMock()
_tech_analysis_mock = MagicMock()

sys.modules.setdefault("alerts",             _alerts_mock)
sys.modules.setdefault("data_feeds",         _data_feeds_mock)
sys.modules.setdefault("technical_analysis", _tech_analysis_mock)

with patch("builtins.open", mock_open(read_data=json.dumps(SYMBOLS_FIXTURE))):
    from main import load_symbols, load_previous_signals, save_signals, SIGNAL_FILE


# ===========================================================================
# load_symbols
# ===========================================================================

class TestLoadSymbols:
    def test_returns_stocks_and_crypto(self, tmp_path):
        symbols = {"stocks": ["AAPL", "TSLA"], "crypto": ["BTC/GBP"]}
        f = tmp_path / "symbols.json"
        f.write_text(json.dumps(symbols))
        stocks, crypto = load_symbols(str(f))
        assert stocks == ["AAPL", "TSLA"]
        assert crypto == ["BTC/GBP"]

    def test_missing_stocks_key_returns_empty_list(self, tmp_path):
        f = tmp_path / "symbols.json"
        f.write_text(json.dumps({"crypto": ["BTC/GBP"]}))
        stocks, crypto = load_symbols(str(f))
        assert stocks == []
        assert crypto == ["BTC/GBP"]

    def test_missing_crypto_key_returns_empty_list(self, tmp_path):
        f = tmp_path / "symbols.json"
        f.write_text(json.dumps({"stocks": ["AAPL"]}))
        stocks, crypto = load_symbols(str(f))
        assert stocks == ["AAPL"]
        assert crypto == []

    def test_empty_file_returns_empty_lists(self, tmp_path):
        f = tmp_path / "symbols.json"
        f.write_text(json.dumps({}))
        stocks, crypto = load_symbols(str(f))
        assert stocks == []
        assert crypto == []

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_symbols(str(tmp_path / "nonexistent.json"))

    def test_invalid_json_raises(self, tmp_path):
        f = tmp_path / "symbols.json"
        f.write_text("not valid json {{{")
        with pytest.raises(json.JSONDecodeError):
            load_symbols(str(f))

    def test_multiple_stocks_and_crypto(self, tmp_path):
        symbols = {"stocks": ["AAPL", "TSLA", "BARC.L"], "crypto": ["BTC/GBP", "ETH/GBP", "ETH/BTC"]}
        f = tmp_path / "symbols.json"
        f.write_text(json.dumps(symbols))
        stocks, crypto = load_symbols(str(f))
        assert len(stocks) == 3
        assert len(crypto) == 3


# ===========================================================================
# load_previous_signals
# ===========================================================================

class TestLoadPreviousSignals:
    def test_returns_dict_when_file_exists(self, tmp_path):
        signals = {"BTC/GBP": "some signal", "AAPL": "another signal"}
        signal_file = tmp_path / "signals.json"
        signal_file.write_text(json.dumps(signals))
        with patch("main.SIGNAL_FILE", str(signal_file)):
            result = load_previous_signals()
        assert result == signals

    def test_returns_empty_dict_when_file_missing(self, tmp_path):
        missing = str(tmp_path / "signals.json")
        with patch("main.SIGNAL_FILE", missing):
            result = load_previous_signals()
        assert result == {}

    def test_returns_empty_dict_not_none(self, tmp_path):
        missing = str(tmp_path / "signals.json")
        with patch("main.SIGNAL_FILE", missing):
            result = load_previous_signals()
        assert result is not None
        assert isinstance(result, dict)

    def test_preserves_all_symbols(self, tmp_path):
        signals = {f"SYM{i}": f"signal {i}" for i in range(10)}
        signal_file = tmp_path / "signals.json"
        signal_file.write_text(json.dumps(signals))
        with patch("main.SIGNAL_FILE", str(signal_file)):
            result = load_previous_signals()
        assert len(result) == 10

    def test_returns_empty_dict_for_empty_signals(self, tmp_path):
        signal_file = tmp_path / "signals.json"
        signal_file.write_text(json.dumps({}))
        with patch("main.SIGNAL_FILE", str(signal_file)):
            result = load_previous_signals()
        assert result == {}


# ===========================================================================
# save_signals
# ===========================================================================

class TestSaveSignals:
    def test_file_is_created(self, tmp_path):
        signal_file = tmp_path / "signals.json"
        with patch("main.SIGNAL_FILE", str(signal_file)):
            save_signals({"BTC/GBP": "some signal"})
        assert signal_file.exists()

    def test_saved_content_is_valid_json(self, tmp_path):
        signal_file = tmp_path / "signals.json"
        signals = {"BTC/GBP": "bull signal", "AAPL": "bear signal"}
        with patch("main.SIGNAL_FILE", str(signal_file)):
            save_signals(signals)
        content = json.loads(signal_file.read_text())
        assert content == signals

    def test_save_then_load_roundtrip(self, tmp_path):
        signal_file = tmp_path / "signals.json"
        signals = {"ETH/GBP": "signal A", "TSLA": "signal B"}
        with patch("main.SIGNAL_FILE", str(signal_file)):
            save_signals(signals)
            result = load_previous_signals()
        assert result == signals

    def test_overwrites_existing_file(self, tmp_path):
        signal_file = tmp_path / "signals.json"
        signal_file.write_text(json.dumps({"OLD": "old signal"}))
        new_signals = {"NEW": "new signal"}
        with patch("main.SIGNAL_FILE", str(signal_file)):
            save_signals(new_signals)
            result = load_previous_signals()
        assert "OLD" not in result
        assert result == new_signals

    def test_saves_empty_dict(self, tmp_path):
        signal_file = tmp_path / "signals.json"
        with patch("main.SIGNAL_FILE", str(signal_file)):
            save_signals({})
            result = load_previous_signals()
        assert result == {}

    def test_output_is_indented(self, tmp_path):
        """Verify the file is pretty-printed (indent=2) for readability."""
        signal_file = tmp_path / "signals.json"
        with patch("main.SIGNAL_FILE", str(signal_file)):
            save_signals({"BTC/GBP": "signal"})
        raw = signal_file.read_text()
        assert "\n" in raw