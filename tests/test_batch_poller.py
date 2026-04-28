import pytest
from unittest.mock import patch, MagicMock
from data.fmp_batch_poller import FMPBatchPoller


class TestSubscribe:
    def test_adds_ticker_to_refcount(self):
        p = FMPBatchPoller()
        p.subscribe("AAPL")
        assert "AAPL" in p._refcount
        assert p._refcount["AAPL"] == 1

    def test_normalizes_to_uppercase(self):
        p = FMPBatchPoller()
        p.subscribe("aapl")
        assert "AAPL" in p._refcount
        assert "aapl" not in p._refcount

    def test_increments_on_second_subscribe(self):
        p = FMPBatchPoller()
        p.subscribe("AAPL")
        p.subscribe("AAPL")
        assert p._refcount["AAPL"] == 2

    def test_multiple_tickers_tracked_independently(self):
        p = FMPBatchPoller()
        p.subscribe("AAPL")
        p.subscribe("TSLA")
        assert p._refcount["AAPL"] == 1
        assert p._refcount["TSLA"] == 1


class TestUnsubscribe:
    def test_decrements_refcount(self):
        p = FMPBatchPoller()
        p.subscribe("AAPL")
        p.subscribe("AAPL")
        p.unsubscribe("AAPL")
        assert p._refcount["AAPL"] == 1

    def test_removes_ticker_when_count_reaches_zero(self):
        p = FMPBatchPoller()
        p.subscribe("AAPL")
        p.unsubscribe("AAPL")
        assert "AAPL" not in p._refcount

    def test_nonexistent_ticker_does_not_raise(self):
        p = FMPBatchPoller()
        p.unsubscribe("FAKE")  # should not raise
        assert "FAKE" not in p._refcount

    def test_normalizes_to_uppercase(self):
        p = FMPBatchPoller()
        p.subscribe("AAPL")
        p.unsubscribe("aapl")
        assert "AAPL" not in p._refcount


class TestStartStop:
    def test_start_sets_running_true(self):
        p = FMPBatchPoller()
        p.start()
        assert p._running is True
        p.stop()

    def test_stop_sets_running_false(self):
        p = FMPBatchPoller()
        p.start()
        p.stop()
        assert p._running is False


class TestFetchBatch:
    def _mock_response(self, data, status=200):
        mock_r = MagicMock()
        mock_r.status_code = status
        mock_r.json.return_value = data
        return mock_r

    def test_calls_on_trade_for_each_ticker(self):
        trades = []
        p = FMPBatchPoller(on_trade=lambda t, price, sz, ts: trades.append((t, price)))
        resp = self._mock_response([
            {"symbol": "AAPL", "price": 150.0},
            {"symbol": "TSLA", "price": 200.0},
        ])
        with patch("requests.get", return_value=resp):
            p._fetch_batch(["AAPL", "TSLA"])
        assert ("AAPL", 150.0) in trades
        assert ("TSLA", 200.0) in trades

    def test_price_passed_as_float(self):
        prices = []
        p = FMPBatchPoller(on_trade=lambda t, price, sz, ts: prices.append(price))
        resp = self._mock_response([{"symbol": "AAPL", "price": 150}])
        with patch("requests.get", return_value=resp):
            p._fetch_batch(["AAPL"])
        assert isinstance(prices[0], float)

    def test_skips_entry_with_no_price(self):
        trades = []
        p = FMPBatchPoller(on_trade=lambda t, price, sz, ts: trades.append(t))
        resp = self._mock_response([
            {"symbol": "AAPL", "price": None},
            {"symbol": "TSLA", "price": 200.0},
        ])
        with patch("requests.get", return_value=resp):
            p._fetch_batch(["AAPL", "TSLA"])
        assert "AAPL" not in trades
        assert "TSLA" in trades

    def test_skips_entry_with_no_symbol(self):
        trades = []
        p = FMPBatchPoller(on_trade=lambda t, price, sz, ts: trades.append(t))
        resp = self._mock_response([
            {"price": 150.0},  # no symbol
            {"symbol": "TSLA", "price": 200.0},
        ])
        with patch("requests.get", return_value=resp):
            p._fetch_batch(["TSLA"])
        assert len(trades) == 1
        assert "TSLA" in trades

    def test_non_200_status_no_on_trade(self):
        mock_on_trade = MagicMock()
        p = FMPBatchPoller(on_trade=mock_on_trade)
        resp = self._mock_response([], status=401)
        with patch("requests.get", return_value=resp):
            p._fetch_batch(["AAPL"])
        mock_on_trade.assert_not_called()

    def test_non_list_response_no_on_trade(self):
        mock_on_trade = MagicMock()
        p = FMPBatchPoller(on_trade=mock_on_trade)
        resp = self._mock_response({"error": "bad request"})
        with patch("requests.get", return_value=resp):
            p._fetch_batch(["AAPL"])
        mock_on_trade.assert_not_called()

    def test_network_exception_does_not_raise(self):
        p = FMPBatchPoller(on_trade=MagicMock())
        with patch("requests.get", side_effect=Exception("timeout")):
            p._fetch_batch(["AAPL"])  # must not raise

    def test_no_on_trade_callback_does_not_raise(self):
        p = FMPBatchPoller(on_trade=None)
        resp = self._mock_response([{"symbol": "AAPL", "price": 150.0}])
        with patch("requests.get", return_value=resp):
            p._fetch_batch(["AAPL"])  # must not raise
