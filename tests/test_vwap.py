import pytest
from unittest.mock import patch, MagicMock
from data.vwap import compute_vwap


def _make_bar(t, high, low, close, volume):
    return {"time": t, "high": high, "low": low, "close": close, "volume": volume}


# Use valid HHMM boundaries: 0 = 00:00, 2359 = 23:59
# _hhmm always returns 700 (07:00), which is inside [0, 2359]
_PATCH_RTH_WIDE  = ("data.vwap._RTH_START", 0,    "data.vwap._RTH_END", 2359)
_PATCH_RTH_NARROW = ("data.vwap._RTH_START", 1000, "data.vwap._RTH_END", 1100)


def _wide_rth(bars):
    return (
        patch("data.vwap.fetch_bars", return_value=bars),
        patch("data.vwap._hhmm", side_effect=lambda t: 700),
        patch("data.vwap._RTH_START", 0),
        patch("data.vwap._RTH_END", 2359),
    )


class TestComputeVWAP:
    def test_empty_bars_returns_empty(self):
        with patch("data.vwap.fetch_bars", return_value=[]), \
             patch("data.vwap._hhmm", side_effect=lambda t: 700), \
             patch("data.vwap._RTH_START", 0), \
             patch("data.vwap._RTH_END", 2359):
            result = compute_vwap(MagicMock(), "AAPL")
        assert result == []

    def test_all_bars_outside_rth_returns_empty(self):
        bars = [_make_bar(1000, 102.0, 100.0, 101.0, 1000)]
        # _hhmm returns 700, RTH is 1000–1100 → 700 excluded
        with patch("data.vwap.fetch_bars", return_value=bars), \
             patch("data.vwap._hhmm", side_effect=lambda t: 700), \
             patch("data.vwap._RTH_START", 1000), \
             patch("data.vwap._RTH_END", 1100):
            result = compute_vwap(MagicMock(), "AAPL")
        assert result == []

    def test_single_bar_vwap_equals_typical(self):
        # typical = (102 + 100 + 101) / 3 = 101.0
        bars = [_make_bar(1000, 102.0, 100.0, 101.0, 1000)]
        with patch("data.vwap.fetch_bars", return_value=bars), \
             patch("data.vwap._hhmm", side_effect=lambda t: 700), \
             patch("data.vwap._RTH_START", 0), \
             patch("data.vwap._RTH_END", 2359):
            result = compute_vwap(MagicMock(), "AAPL")
        assert len(result) == 1
        assert result[0]["value"] == 101.0
        assert result[0]["time"] == 1000

    def test_two_bars_running_vwap(self):
        # Bar 1: typical=(102+100+101)/3=101.0, vol=1000 → vwap=101.0
        # Bar 2: typical=(104+102+103)/3=103.0, vol=2000
        #        vwap = (101*1000 + 103*2000) / 3000 = 307000/3000 = 102.33
        bars = [
            _make_bar(1000, 102.0, 100.0, 101.0, 1000),
            _make_bar(1060, 104.0, 102.0, 103.0, 2000),
        ]
        with patch("data.vwap.fetch_bars", return_value=bars), \
             patch("data.vwap._hhmm", side_effect=lambda t: 700), \
             patch("data.vwap._RTH_START", 0), \
             patch("data.vwap._RTH_END", 2359):
            result = compute_vwap(MagicMock(), "AAPL")
        assert len(result) == 2
        assert result[0]["value"] == 101.0
        assert result[1]["value"] == round((101.0 * 1000 + 103.0 * 2000) / 3000, 2)

    def test_zero_volume_bar_skipped_in_output(self):
        # cum_vol stays 0 for zero-volume bar → condition `if cum_vol > 0` is False → not appended
        bars = [
            _make_bar(1000, 102.0, 100.0, 101.0, 0),
            _make_bar(1060, 104.0, 102.0, 103.0, 1000),
        ]
        with patch("data.vwap.fetch_bars", return_value=bars), \
             patch("data.vwap._hhmm", side_effect=lambda t: 700), \
             patch("data.vwap._RTH_START", 0), \
             patch("data.vwap._RTH_END", 2359):
            result = compute_vwap(MagicMock(), "AAPL")
        assert len(result) == 1
        assert result[0]["time"] == 1060

    def test_result_times_match_bar_times(self):
        bars = [_make_bar(t, 102.0, 100.0, 101.0, 500) for t in [1000, 1060, 1120]]
        with patch("data.vwap.fetch_bars", return_value=bars), \
             patch("data.vwap._hhmm", side_effect=lambda t: 700), \
             patch("data.vwap._RTH_START", 0), \
             patch("data.vwap._RTH_END", 2359):
            result = compute_vwap(MagicMock(), "AAPL")
        assert [r["time"] for r in result] == [1000, 1060, 1120]

    def test_vwap_values_rounded_to_two_decimals(self):
        # typical = (100.001 + 99.999 + 100.001) / 3 = 100.000333...
        bars = [_make_bar(1000, 100.001, 99.999, 100.001, 1000)]
        with patch("data.vwap.fetch_bars", return_value=bars), \
             patch("data.vwap._hhmm", side_effect=lambda t: 700), \
             patch("data.vwap._RTH_START", 0), \
             patch("data.vwap._RTH_END", 2359):
            result = compute_vwap(MagicMock(), "AAPL")
        assert result[0]["value"] == round((100.001 + 99.999 + 100.001) / 3, 2)

    def test_vwap_increases_with_higher_price_bar(self):
        bars = [
            _make_bar(1000, 100.0, 98.0, 99.0, 1000),
            _make_bar(1060, 200.0, 198.0, 199.0, 1000),
        ]
        with patch("data.vwap.fetch_bars", return_value=bars), \
             patch("data.vwap._hhmm", side_effect=lambda t: 700), \
             patch("data.vwap._RTH_START", 0), \
             patch("data.vwap._RTH_END", 2359):
            result = compute_vwap(MagicMock(), "AAPL")
        assert result[1]["value"] > result[0]["value"]
