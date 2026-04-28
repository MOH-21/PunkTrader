import json
import os
import time
import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock

import pytz

ET = pytz.timezone("America/New_York")
_FIXED_ET = ET.localize(datetime(2026, 4, 28, 10, 0, 0))
_FIXED_DATE = _FIXED_ET.date()


@pytest.fixture
def cache_dir(tmp_path):
    with patch("levels.cache._CACHE_DIR", str(tmp_path)):
        yield tmp_path


@pytest.fixture
def fixed_time(cache_dir):
    with patch("levels.cache._current_et_time", return_value=_FIXED_ET):
        yield _FIXED_ET


def _cache_file(tmp_path):
    return tmp_path / f"levels_{_FIXED_DATE.strftime('%Y-%m-%d')}.json"


ALL_LEVELS = {
    "PDH": 500.0, "PDL": 495.0,
    "PMH": 498.0, "PML": 493.0,
    "ORH": 501.0, "ORL": 494.0,
}


class TestCacheGet:
    def test_returns_none_when_no_file(self, fixed_time):
        from levels import cache
        assert cache.get("AAPL") is None

    def test_returns_none_for_unknown_ticker(self, fixed_time, tmp_path):
        from levels import cache
        cache.set("AAPL", ALL_LEVELS)
        assert cache.get("TSLA") is None

    def test_returns_correct_values(self, fixed_time):
        from levels import cache
        cache.set("AAPL", ALL_LEVELS)
        result = cache.get("AAPL")
        assert result["PDH"] == 500.0
        assert result["PDL"] == 495.0
        assert result["ORH"] == 501.0

    def test_returns_none_for_missing_levels(self, fixed_time):
        from levels import cache
        cache.set("AAPL", {"PDH": 500.0})
        result = cache.get("AAPL")
        assert result["PDH"] == 500.0
        assert result["PDL"] is None
        assert result["PMH"] is None

    def test_corrupted_json_returns_none(self, fixed_time, tmp_path):
        from levels import cache
        f = _cache_file(tmp_path)
        f.write_text("not valid json {{{")
        assert cache.get("AAPL") is None

    def test_none_value_round_trips(self, fixed_time):
        from levels import cache
        cache.set("AAPL", {"PDH": 500.0, "PDL": None})
        result = cache.get("AAPL")
        assert result["PDH"] == 500.0
        assert result["PDL"] is None


class TestCacheSet:
    def test_creates_file(self, fixed_time, tmp_path):
        from levels import cache
        cache.set("AAPL", ALL_LEVELS)
        assert _cache_file(tmp_path).exists()

    def test_multiple_tickers_same_file(self, fixed_time, tmp_path):
        from levels import cache
        cache.set("AAPL", ALL_LEVELS)
        cache.set("TSLA", {"PDH": 200.0})
        data = json.loads(_cache_file(tmp_path).read_text())
        assert "AAPL" in data
        assert "TSLA" in data

    def test_update_existing_ticker(self, fixed_time):
        from levels import cache
        cache.set("AAPL", {"PDH": 500.0})
        cache.set("AAPL", {"PDH": 510.0})
        result = cache.get("AAPL")
        assert result["PDH"] == 510.0

    def test_atomic_write_no_tmp_file_left(self, fixed_time, tmp_path):
        from levels import cache
        cache.set("AAPL", ALL_LEVELS)
        tmp_files = list(tmp_path.glob("*.tmp"))
        assert len(tmp_files) == 0

    def test_ignores_unknown_level_names(self, fixed_time, tmp_path):
        from levels import cache
        cache.set("AAPL", {"PDH": 500.0, "UNKNOWN_KEY": 999.0})
        data = json.loads(_cache_file(tmp_path).read_text())
        entry = data["AAPL"]
        assert "UNKNOWN_KEY" not in entry


class TestIsLocked:
    def test_pdh_always_locked(self):
        from levels import cache
        early = ET.localize(datetime(2026, 4, 28, 7, 0, 0))
        with patch("levels.cache._current_et_time", return_value=early):
            assert cache.is_locked("PDH") is True
            assert cache.is_locked("PDL") is True

    def test_pmh_unlocked_before_930(self):
        from levels import cache
        t = ET.localize(datetime(2026, 4, 28, 9, 29, 0))
        with patch("levels.cache._current_et_time", return_value=t):
            assert cache.is_locked("PMH") is False
            assert cache.is_locked("PML") is False

    def test_pmh_locked_at_930(self):
        from levels import cache
        t = ET.localize(datetime(2026, 4, 28, 9, 30, 0))
        with patch("levels.cache._current_et_time", return_value=t):
            assert cache.is_locked("PMH") is True
            assert cache.is_locked("PML") is True

    def test_orh_unlocked_before_935(self):
        from levels import cache
        t = ET.localize(datetime(2026, 4, 28, 9, 34, 0))
        with patch("levels.cache._current_et_time", return_value=t):
            assert cache.is_locked("ORH") is False
            assert cache.is_locked("ORL") is False

    def test_orh_locked_at_935(self):
        from levels import cache
        t = ET.localize(datetime(2026, 4, 28, 9, 35, 0))
        with patch("levels.cache._current_et_time", return_value=t):
            assert cache.is_locked("ORH") is True
            assert cache.is_locked("ORL") is True

    def test_unknown_level_not_locked(self):
        from levels import cache
        t = ET.localize(datetime(2026, 4, 28, 12, 0, 0))
        with patch("levels.cache._current_et_time", return_value=t):
            assert cache.is_locked("UNKNOWN") is False


class TestPurgeOld:
    def test_removes_files_older_than_7_days(self, tmp_path):
        from levels import cache
        old_file = tmp_path / "levels_2020-01-01.json"
        old_file.write_text("{}")
        old_mtime = time.time() - 10 * 86400
        os.utime(str(old_file), (old_mtime, old_mtime))

        recent_file = tmp_path / "levels_2026-04-27.json"
        recent_file.write_text("{}")

        with patch("levels.cache._CACHE_DIR", str(tmp_path)):
            cache.purge_old()

        assert not old_file.exists()
        assert recent_file.exists()

    def test_skips_non_levels_files(self, tmp_path):
        from levels import cache
        other = tmp_path / "other_file.json"
        other.write_text("{}")
        old_mtime = time.time() - 10 * 86400
        os.utime(str(other), (old_mtime, old_mtime))

        with patch("levels.cache._CACHE_DIR", str(tmp_path)):
            cache.purge_old()

        assert other.exists()
