import pytest
from data.candle_builder import CandleBuilder

# All timestamps chosen so adjacent ones land in same or different 60s buckets.
# bar_time = (epoch // 60) * 60
T0 = 1700000060  # bar_time = 1700000040
T1 = T0 + 10    # same minute
T2 = T0 + 60    # next minute, bar_time = 1700000100


class TestFirstTrade:
    def test_creates_candle_with_correct_ohlcv(self):
        cb = CandleBuilder()
        candle, is_new = cb.on_trade("AAPL", 150.0, 100, T0)
        assert candle["open"] == 150.0
        assert candle["high"] == 150.0
        assert candle["low"] == 150.0
        assert candle["close"] == 150.0
        assert candle["volume"] == 100

    def test_bar_time_bucketed_to_minute(self):
        cb = CandleBuilder()
        candle, _ = cb.on_trade("AAPL", 150.0, 100, T0)
        assert candle["time"] == (T0 // 60) * 60

    def test_is_new_false_for_first_trade(self):
        # No previous candle → is_new must be False (nothing to close)
        cb = CandleBuilder()
        _, is_new = cb.on_trade("AAPL", 150.0, 100, T0)
        assert is_new is False

    def test_independent_tickers(self):
        cb = CandleBuilder()
        cb.on_trade("AAPL", 150.0, 100, T0)
        cb.on_trade("TSLA", 200.0, 50, T0)
        assert cb.get_candle("AAPL")["close"] == 150.0
        assert cb.get_candle("TSLA")["close"] == 200.0


class TestSameMinuteUpdate:
    def test_is_new_false(self):
        cb = CandleBuilder()
        cb.on_trade("AAPL", 150.0, 100, T0)
        _, is_new = cb.on_trade("AAPL", 155.0, 50, T1)
        assert is_new is False

    def test_high_updated(self):
        cb = CandleBuilder()
        cb.on_trade("AAPL", 150.0, 100, T0)
        candle, _ = cb.on_trade("AAPL", 155.0, 50, T1)
        assert candle["high"] == 155.0

    def test_low_updated(self):
        cb = CandleBuilder()
        cb.on_trade("AAPL", 150.0, 100, T0)
        candle, _ = cb.on_trade("AAPL", 145.0, 50, T1)
        assert candle["low"] == 145.0

    def test_close_updated(self):
        cb = CandleBuilder()
        cb.on_trade("AAPL", 150.0, 100, T0)
        candle, _ = cb.on_trade("AAPL", 152.0, 50, T1)
        assert candle["close"] == 152.0

    def test_open_unchanged(self):
        cb = CandleBuilder()
        cb.on_trade("AAPL", 150.0, 100, T0)
        candle, _ = cb.on_trade("AAPL", 152.0, 50, T1)
        assert candle["open"] == 150.0

    def test_volume_accumulates(self):
        cb = CandleBuilder()
        cb.on_trade("AAPL", 150.0, 100, T0)
        candle, _ = cb.on_trade("AAPL", 152.0, 50, T1)
        assert candle["volume"] == 150

    def test_high_low_across_three_trades(self):
        cb = CandleBuilder()
        cb.on_trade("AAPL", 150.0, 10, T0)
        cb.on_trade("AAPL", 145.0, 10, T1)
        candle, _ = cb.on_trade("AAPL", 155.0, 10, T1 + 5)
        assert candle["high"] == 155.0
        assert candle["low"] == 145.0
        assert candle["open"] == 150.0
        assert candle["close"] == 155.0


class TestNewMinute:
    def test_is_new_true_on_rollover(self):
        cb = CandleBuilder()
        cb.on_trade("AAPL", 150.0, 100, T0)
        _, is_new = cb.on_trade("AAPL", 160.0, 50, T2)
        assert is_new is True

    def test_new_candle_starts_fresh(self):
        cb = CandleBuilder()
        cb.on_trade("AAPL", 150.0, 100, T0)
        candle, _ = cb.on_trade("AAPL", 160.0, 50, T2)
        assert candle["open"] == 160.0
        assert candle["high"] == 160.0
        assert candle["low"] == 160.0
        assert candle["volume"] == 50

    def test_new_bar_time_correct(self):
        cb = CandleBuilder()
        cb.on_trade("AAPL", 150.0, 100, T0)
        candle, _ = cb.on_trade("AAPL", 160.0, 50, T2)
        assert candle["time"] == (T2 // 60) * 60


class TestGetCandle:
    def test_returns_none_for_unknown_ticker(self):
        cb = CandleBuilder()
        assert cb.get_candle("FAKE") is None

    def test_returns_copy_not_reference(self):
        cb = CandleBuilder()
        cb.on_trade("AAPL", 150.0, 100, T0)
        c = cb.get_candle("AAPL")
        c["open"] = 999.0
        assert cb.get_candle("AAPL")["open"] == 150.0


class TestOnBar:
    def test_on_bar_replaces_candle(self):
        cb = CandleBuilder()
        cb.on_trade("AAPL", 150.0, 100, T0)
        bar = {"time": (T0 // 60) * 60, "open": 148.0, "high": 153.0,
               "low": 147.0, "close": 151.0, "volume": 5000}
        cb.on_bar("AAPL", bar)
        c = cb.get_candle("AAPL")
        assert c["open"] == 148.0
        assert c["volume"] == 5000

    def test_on_bar_creates_candle_for_new_ticker(self):
        cb = CandleBuilder()
        bar = {"time": T0, "open": 100.0, "high": 105.0,
               "low": 99.0, "close": 102.0, "volume": 1000}
        cb.on_bar("TSLA", bar)
        assert cb.get_candle("TSLA")["close"] == 102.0
