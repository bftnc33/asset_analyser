"""
Unit tests for data_feeds.py.

Both fetch_crypto_data and fetch_stock_data make external network calls, so
all exchange/yfinance interactions are patched. No real HTTP requests are made.

sys.modules cleanup ensures we get the real module even when test_main.py
has registered a mock under the 'data_feeds' key.
"""

import sys
import pandas as pd
import pytest
from unittest.mock import patch, MagicMock

# Remove any mock registered by test_main.py so we import the real module
sys.modules.pop("data_feeds", None)

import data_feeds
from data_feeds import fetch_crypto_data, fetch_stock_data


# ===========================================================================
# Shared helpers
# ===========================================================================

def make_ohlcv_rows(n=10, base_ts=1_700_000_000_000):
    """Return n rows of fake OHLCV data in ccxt list format."""
    return [
        [base_ts + i * 86_400_000, 100 + i, 105 + i, 95 + i, 102 + i, 1000 + i]
        for i in range(n)
    ]


def make_simple_yfinance_df(n=10):
    """Return a yfinance-style DataFrame with flat (non-MultiIndex) columns."""
    dates = pd.date_range("2024-01-01", periods=n, freq="D", name="Date")
    return pd.DataFrame({
        "Close":  [150.0 + i for i in range(n)],
        "Open":   [149.0 + i for i in range(n)],
        "High":   [152.0 + i for i in range(n)],
        "Low":    [148.0 + i for i in range(n)],
        "Volume": [1_000_000 + i for i in range(n)],
    }, index=dates)


def make_multiindex_yfinance_df(n=10, ticker="AAPL"):
    """Return a yfinance-style DataFrame with MultiIndex columns."""
    dates = pd.date_range("2024-01-01", periods=n, freq="D", name="Date")
    columns = pd.MultiIndex.from_arrays([
        ["Close", "Open", "High", "Low", "Volume"],
        [ticker] * 5,
    ])
    data = {
        ("Close",  ticker): [150.0 + i for i in range(n)],
        ("Open",   ticker): [149.0 + i for i in range(n)],
        ("High",   ticker): [152.0 + i for i in range(n)],
        ("Low",    ticker): [148.0 + i for i in range(n)],
        ("Volume", ticker): [1_000_000 + i for i in range(n)],
    }
    return pd.DataFrame(data, index=dates, columns=columns)


# ===========================================================================
# fetch_crypto_data
# ===========================================================================

class TestFetchCryptoData:
    def test_returns_dataframe(self):
        with patch.object(data_feeds.crypto_exchange, "fetch_ohlcv", return_value=make_ohlcv_rows()):
            df = fetch_crypto_data("BTC/GBP")
        assert isinstance(df, pd.DataFrame)

    def test_correct_columns_present(self):
        with patch.object(data_feeds.crypto_exchange, "fetch_ohlcv", return_value=make_ohlcv_rows()):
            df = fetch_crypto_data("BTC/GBP")
        assert set(["open", "high", "low", "close", "volume"]).issubset(df.columns)

    def test_timestamp_is_index(self):
        with patch.object(data_feeds.crypto_exchange, "fetch_ohlcv", return_value=make_ohlcv_rows()):
            df = fetch_crypto_data("BTC/GBP")
        assert df.index.name == "timestamp"

    def test_index_is_datetime(self):
        with patch.object(data_feeds.crypto_exchange, "fetch_ohlcv", return_value=make_ohlcv_rows()):
            df = fetch_crypto_data("BTC/GBP")
        assert pd.api.types.is_datetime64_any_dtype(df.index)

    def test_row_count_matches_ohlcv(self):
        rows = make_ohlcv_rows(25)
        with patch.object(data_feeds.crypto_exchange, "fetch_ohlcv", return_value=rows):
            df = fetch_crypto_data("ETH/GBP")
        assert len(df) == 25

    def test_close_values_correct(self):
        rows = make_ohlcv_rows(5)
        with patch.object(data_feeds.crypto_exchange, "fetch_ohlcv", return_value=rows):
            df = fetch_crypto_data("BTC/GBP")
        expected_closes = [row[4] for row in rows]
        assert list(df["close"]) == expected_closes

    def test_calls_exchange_with_correct_symbol(self):
        with patch.object(data_feeds.crypto_exchange, "fetch_ohlcv", return_value=make_ohlcv_rows()) as mock:
            fetch_crypto_data("ETH/BTC")
        mock.assert_called_once()
        assert mock.call_args[0][0] == "ETH/BTC"

    def test_calls_exchange_with_daily_timeframe(self):
        with patch.object(data_feeds.crypto_exchange, "fetch_ohlcv", return_value=make_ohlcv_rows()) as mock:
            fetch_crypto_data("BTC/GBP")
        assert mock.call_args[1].get("timeframe") == "1d"

    def test_exchange_error_propagates(self):
        with patch.object(data_feeds.crypto_exchange, "fetch_ohlcv", side_effect=Exception("Network error")):
            with pytest.raises(Exception, match="Network error"):
                fetch_crypto_data("BTC/GBP")

    def test_empty_response_returns_empty_df(self):
        with patch.object(data_feeds.crypto_exchange, "fetch_ohlcv", return_value=[]):
            df = fetch_crypto_data("BTC/GBP")
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 0


# ===========================================================================
# fetch_stock_data
# ===========================================================================

class TestFetchStockData:
    def test_returns_dataframe(self):
        with patch.object(data_feeds.yf, "download", return_value=make_simple_yfinance_df()):
            df = fetch_stock_data("AAPL")
        assert isinstance(df, pd.DataFrame)

    def test_correct_columns_present(self):
        with patch.object(data_feeds.yf, "download", return_value=make_simple_yfinance_df()):
            df = fetch_stock_data("AAPL")
        assert set(["open", "high", "low", "close", "volume"]).issubset(df.columns)

    def test_columns_are_lowercase(self):
        with patch.object(data_feeds.yf, "download", return_value=make_simple_yfinance_df()):
            df = fetch_stock_data("AAPL")
        for col in ["close", "open", "high", "low", "volume"]:
            assert col in df.columns
        for col in ["Close", "Open", "High", "Low", "Volume"]:
            assert col not in df.columns

    def test_index_is_named_timestamp(self):
        with patch.object(data_feeds.yf, "download", return_value=make_simple_yfinance_df()):
            df = fetch_stock_data("AAPL")
        assert df.index.name == "timestamp"

    def test_row_count_preserved(self):
        with patch.object(data_feeds.yf, "download", return_value=make_simple_yfinance_df(20)):
            df = fetch_stock_data("AAPL")
        assert len(df) == 20

    def test_close_values_correct(self):
        raw = make_simple_yfinance_df(5)
        expected_closes = list(raw["Close"])  # capture before function lowercases columns
        with patch.object(data_feeds.yf, "download", return_value=raw):
            df = fetch_stock_data("AAPL")
        assert list(df["close"]) == expected_closes

    def test_multiindex_columns_flattened(self):
        """yfinance sometimes returns MultiIndex columns — should be flattened."""
        with patch.object(data_feeds.yf, "download", return_value=make_multiindex_yfinance_df(ticker="AAPL")):
            df = fetch_stock_data("AAPL")
        assert not isinstance(df.columns, pd.MultiIndex)
        assert "close" in df.columns

    def test_empty_dataframe_raises_value_error(self):
        with patch.object(data_feeds.yf, "download", return_value=pd.DataFrame()):
            with pytest.raises(ValueError, match="No data fetched"):
                fetch_stock_data("INVALID")

    def test_called_with_2y_period(self):
        with patch.object(data_feeds.yf, "download", return_value=make_simple_yfinance_df()) as mock:
            fetch_stock_data("AAPL")
        assert mock.call_args[1].get("period") == "2y"

    def test_called_with_daily_interval(self):
        with patch.object(data_feeds.yf, "download", return_value=make_simple_yfinance_df()) as mock:
            fetch_stock_data("AAPL")
        assert mock.call_args[1].get("interval") == "1d"

    def test_called_with_correct_ticker(self):
        with patch.object(data_feeds.yf, "download", return_value=make_simple_yfinance_df()) as mock:
            fetch_stock_data("BARC.L")
        assert mock.call_args[0][0] == "BARC.L"

    def test_network_error_propagates(self):
        with patch.object(data_feeds.yf, "download", side_effect=Exception("Timeout")):
            with pytest.raises(Exception, match="Timeout"):
                fetch_stock_data("AAPL")

    def test_date_index_renamed_to_timestamp(self):
        with patch.object(data_feeds.yf, "download", return_value=make_simple_yfinance_df()):
            df = fetch_stock_data("AAPL")
        assert df.index.name == "timestamp"
        assert "Date" not in str(df.index.name)