import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytz

from data.fmp_rest import _parse_et_dt, _to_local_epoch, _aggregate_weekly, fetch_bars

ET = pytz.timezone("America/New_York")

# Real UTC epochs for known dates (midnight UTC)
# 2024-01-08 Mon = 1704672000, 2024-01-12 Fri = 1705017600, 2024-01-15 Mon = 1705276800
MON_JAN_8_EPOCH  = int(datetime(2024, 1, 8,  tzinfo=timezone.utc).timestamp())
FRI_JAN_12_EPOCH = int(datetime(2024, 1, 12, tzinfo=timezone.utc).timestamp())
MON_JAN_15_EPOCH = int(datetime(2024, 1, 15, tzinfo=timezone.utc).timestamp())


class MockAPI:
    def __init__(self, data):
        self._data = data
        self.calls = []

    def get(self, path, params=None):
        self.calls.append((path, params))
        return self._data


class TestParseDatetime:
    def test_intraday_format(self):
        dt = _parse_et_dt("2024-01-15 09:30:00")
        assert dt.year == 2024
        assert dt.month == 1
        assert dt.day == 15
        assert dt.hour == 9
        assert dt.minute == 30
        assert dt.second == 0

    def test_daily_format(self):
        dt = _parse_et_dt("2024-01-15")
        assert dt.year == 2024
        assert dt.month == 1
        assert dt.day == 15

    def test_returns_timezone_aware(self):
        dt = _parse_et_dt("2024-01-15 09:30:00")
        assert dt.tzinfo is not None

    def test_et_timezone(self):
        dt = _parse_et_dt("2024-01-15 09:30:00")
        assert dt.tzinfo.zone == "America/New_York"


class TestToLocalEpoch:
    def test_returns_int(self):
        dt_et = ET.localize(datetime(2024, 1, 15, 9, 30, 0))
        result = _to_local_epoch(dt_et)
        assert isinstance(result, int)

    def test_consistent_for_same_input(self):
        dt_et = ET.localize(datetime(2024, 1, 15, 9, 30, 0))
        assert _to_local_epoch(dt_et) == _to_local_epoch(dt_et)

    def test_later_time_has_larger_epoch(self):
        dt1 = ET.localize(datetime(2024, 1, 15, 9, 30, 0))
        dt2 = ET.localize(datetime(2024, 1, 15, 9, 31, 0))
        assert _to_local_epoch(dt2) > _to_local_epoch(dt1)


class TestAggregateWeekly:
    def _bar(self, epoch, open_, high, low, close, volume):
        return {"time": epoch, "open": open_, "high": high,
                "low": low, "close": close, "volume": volume}

    def test_single_bar_one_week(self):
        bars = [self._bar(MON_JAN_8_EPOCH, 100.0, 105.0, 99.0, 103.0, 1000)]
        result = _aggregate_weekly(bars)
        assert len(result) == 1
        assert result[0]["open"] == 100.0

    def test_two_bars_same_week_merged(self):
        bars = [
            self._bar(MON_JAN_8_EPOCH,  98.0, 102.0, 97.0, 101.0, 1000),  # Mon
            self._bar(FRI_JAN_12_EPOCH, 101.0, 106.0, 99.0, 104.0, 2000),  # Fri
        ]
        result = _aggregate_weekly(bars)
        assert len(result) == 1
        w = result[0]
        assert w["open"] == 98.0    # first bar's open
        assert w["close"] == 104.0  # last bar's close
        assert w["high"] == 106.0   # max of both highs
        assert w["low"] == 97.0     # min of both lows
        assert w["volume"] == 3000

    def test_two_different_weeks(self):
        bars = [
            self._bar(MON_JAN_8_EPOCH,  100.0, 105.0, 99.0, 103.0, 1000),
            self._bar(MON_JAN_15_EPOCH, 104.0, 110.0, 103.0, 108.0, 2000),
        ]
        result = _aggregate_weekly(bars)
        assert len(result) == 2

    def test_sorted_chronologically(self):
        bars = [
            self._bar(MON_JAN_15_EPOCH, 104.0, 110.0, 103.0, 108.0, 2000),
            self._bar(MON_JAN_8_EPOCH,  100.0, 105.0,  99.0, 103.0, 1000),
        ]
        result = _aggregate_weekly(bars)
        assert result[0]["time"] < result[1]["time"]

    def test_empty_input(self):
        assert _aggregate_weekly([]) == []

    def test_high_is_max_across_all_bars(self):
        bars = [
            self._bar(MON_JAN_8_EPOCH,  100.0, 105.0, 99.0, 103.0, 500),
            self._bar(FRI_JAN_12_EPOCH, 103.0, 109.0, 102.0, 107.0, 500),
        ]
        result = _aggregate_weekly(bars)
        assert result[0]["high"] == 109.0

    def test_low_is_min_across_all_bars(self):
        bars = [
            self._bar(MON_JAN_8_EPOCH,  100.0, 105.0, 97.0, 103.0, 500),
            self._bar(FRI_JAN_12_EPOCH, 103.0, 108.0, 99.0, 107.0, 500),
        ]
        result = _aggregate_weekly(bars)
        assert result[0]["low"] == 97.0


class TestFetchBars:
    _INTRADAY_RAW = [
        # FMP returns newest first
        {"date": "2024-01-15 09:35:00", "open": "100.5", "high": "101.0",
         "low": "100.0", "close": "100.8", "volume": "2000"},
        {"date": "2024-01-15 09:30:00", "open": "99.5", "high": "100.5",
         "low": "99.0", "close": "100.0", "volume": "1000"},
    ]

    def test_intraday_calls_historical_chart_endpoint(self):
        api = MockAPI(self._INTRADAY_RAW)
        fetch_bars(api, "AAPL", timeframe="5Min")
        assert any("/historical-chart/" in path for path, _ in api.calls)

    def test_intraday_result_sorted_chronologically(self):
        api = MockAPI(self._INTRADAY_RAW)
        result = fetch_bars(api, "AAPL", timeframe="5Min")
        assert len(result) == 2
        assert result[0]["time"] < result[1]["time"]

    def test_intraday_ohlcv_types(self):
        api = MockAPI(self._INTRADAY_RAW)
        result = fetch_bars(api, "AAPL", timeframe="5Min")
        bar = result[0]
        assert isinstance(bar["open"],   float)
        assert isinstance(bar["high"],   float)
        assert isinstance(bar["low"],    float)
        assert isinstance(bar["close"],  float)
        assert isinstance(bar["volume"], int)
        assert isinstance(bar["time"],   int)

    def test_daily_calls_eod_endpoint(self):
        daily_raw = [
            {"date": "2024-01-15", "open": "100.0", "high": "105.0",
             "low": "99.0", "close": "103.0", "volume": "5000000"},
        ]
        api = MockAPI(daily_raw)
        fetch_bars(api, "AAPL", timeframe="1Day")
        assert any("/historical-price-eod/full" in path for path, _ in api.calls)

    def test_skips_bars_with_bad_numeric_data(self):
        raw = [
            {"date": "2024-01-15 09:35:00", "open": "bad", "high": "101.0",
             "low": "100.0", "close": "100.8", "volume": "2000"},
            {"date": "2024-01-15 09:30:00", "open": "99.5", "high": "100.5",
             "low": "99.0", "close": "100.0", "volume": "1000"},
        ]
        api = MockAPI(raw)
        result = fetch_bars(api, "AAPL", timeframe="5Min")
        # reversed([bad_0935, ok_0930]) → [ok_0930, bad_0935]
        # ok_0930 → passes, bad_0935 → ValueError → skipped
        assert len(result) == 1
        assert result[0]["close"] == 100.0

    def test_skips_bars_with_missing_date_key(self):
        raw = [
            {"open": "100.0", "high": "101.0", "low": "99.0", "close": "100.5", "volume": "1000"},
            {"date": "2024-01-15 09:30:00", "open": "99.5", "high": "100.5",
             "low": "99.0", "close": "100.0", "volume": "1000"},
        ]
        api = MockAPI(raw)
        result = fetch_bars(api, "AAPL", timeframe="5Min")
        assert len(result) == 1

    def test_empty_response_returns_empty_list(self):
        api = MockAPI([])
        result = fetch_bars(api, "AAPL", timeframe="5Min")
        assert result == []

    def test_non_list_response_returns_empty_list(self):
        api = MockAPI({"error": "something"})
        result = fetch_bars(api, "AAPL", timeframe="5Min")
        assert result == []

    def test_weekly_aggregates_daily_bars(self):
        # Patch TZ=UTC so the fake-UTC epoch stores midnight UTC for each date.
        # Without this, e.g. PST shifts "2024-01-08 00:00 ET" to "2024-01-07 21:00"
        # which _aggregate_weekly reads as Sunday → wrong ISO week.
        daily_raw = [
            # FMP returns newest first
            {"date": "2024-01-12", "open": "101.0", "high": "106.0",
             "low": "100.0", "close": "104.0", "volume": "2000000"},  # Fri
            {"date": "2024-01-08", "open": "98.0", "high": "103.0",
             "low": "97.0", "close": "101.0", "volume": "1000000"},   # Mon
        ]
        api = MockAPI(daily_raw)
        import pytz
        with patch("data.fmp_rest.TZ", pytz.UTC):
            result = fetch_bars(api, "AAPL", timeframe="1Week")
        assert len(result) == 1
        w = result[0]
        assert w["open"] == 98.0    # Mon open
        assert w["close"] == 104.0  # Fri close
        assert w["high"] == 106.0
        assert w["low"] == 97.0

    def test_values_rounded_to_two_decimals(self):
        raw = [
            {"date": "2024-01-15 09:30:00", "open": "99.555", "high": "100.555",
             "low": "99.444", "close": "100.555", "volume": "1000"},
        ]
        api = MockAPI(raw)
        result = fetch_bars(api, "AAPL", timeframe="5Min")
        assert result[0]["open"] == round(99.555, 2)
        assert result[0]["close"] == round(100.555, 2)

    def test_volume_defaults_to_zero_when_missing(self):
        raw = [
            {"date": "2024-01-15 09:30:00", "open": "100.0", "high": "101.0",
             "low": "99.0", "close": "100.5"},
        ]
        api = MockAPI(raw)
        result = fetch_bars(api, "AAPL", timeframe="5Min")
        assert result[0]["volume"] == 0
