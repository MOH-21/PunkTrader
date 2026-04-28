import pytest
from unittest.mock import patch, MagicMock


class TestIndexRoute:
    def test_returns_200(self, client):
        resp = client.get("/")
        assert resp.status_code == 200

    def test_returns_html(self, client):
        resp = client.get("/")
        assert b"<html" in resp.data.lower() or b"<!doctype" in resp.data.lower()


class TestSettingsRoute:
    def test_get_returns_200(self, client):
        resp = client.get("/settings")
        assert resp.status_code == 200

    def test_post_redirects(self, client, tmp_path):
        env_file = tmp_path / ".env"
        with patch("app._ENV_PATH", str(env_file)):
            resp = client.post("/settings", data={
                "fmp_api_key": "test_key_123",
                "timezone": "America/New_York",
                "default_ticker": "AAPL",
                "watchlist": "AAPL,TSLA",
            })
        assert resp.status_code == 302

    def test_post_redirect_target(self, client, tmp_path):
        env_file = tmp_path / ".env"
        with patch("app._ENV_PATH", str(env_file)):
            resp = client.post("/settings", data={
                "fmp_api_key": "key",
                "timezone": "America/New_York",
                "default_ticker": "SPY",
                "watchlist": "SPY",
            }, follow_redirects=False)
        assert "/settings" in resp.headers.get("Location", "")


class TestApiBars:
    _MOCK_BARS = [
        {"time": 1000, "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.5, "volume": 1000}
    ]

    def test_success_returns_200(self, client):
        with patch("app.get_api", return_value=MagicMock()), \
             patch("app.fetch_bars", return_value=self._MOCK_BARS):
            resp = client.get("/api/bars/AAPL?timeframe=5Min")
        assert resp.status_code == 200

    def test_success_returns_list(self, client):
        with patch("app.get_api", return_value=MagicMock()), \
             patch("app.fetch_bars", return_value=self._MOCK_BARS):
            resp = client.get("/api/bars/AAPL?timeframe=5Min")
        data = resp.get_json()
        assert isinstance(data, list)
        assert data[0]["close"] == 100.5

    def test_ticker_uppercased(self, client):
        captured = {}

        def mock_fetch(api, ticker, **kwargs):
            captured["ticker"] = ticker
            return []

        with patch("app.get_api", return_value=MagicMock()), \
             patch("app.fetch_bars", side_effect=mock_fetch):
            client.get("/api/bars/aapl")
        assert captured["ticker"] == "AAPL"

    def test_error_returns_400(self, client):
        with patch("app.get_api", side_effect=Exception("no key")):
            resp = client.get("/api/bars/AAPL")
        assert resp.status_code == 400
        assert "error" in resp.get_json()

    def test_default_timeframe_is_5min(self, client):
        captured = {}

        def mock_fetch(api, ticker, timeframe="5Min", **kwargs):
            captured["timeframe"] = timeframe
            return []

        with patch("app.get_api", return_value=MagicMock()), \
             patch("app.fetch_bars", side_effect=mock_fetch):
            client.get("/api/bars/AAPL")
        assert captured["timeframe"] == "5Min"


class TestApiLevels:
    _MOCK_LEVELS = {
        "PDH": 500.0, "PDL": 490.0,
        "PMH": 498.0, "PML": 492.0,
        "ORH": 501.0, "ORL": 493.0,
    }

    def test_success_returns_200(self, client):
        with patch("app.get_api", return_value=MagicMock()), \
             patch("app.get_levels", return_value=self._MOCK_LEVELS):
            resp = client.get("/api/levels/AAPL")
        assert resp.status_code == 200

    def test_returns_level_values(self, client):
        with patch("app.get_api", return_value=MagicMock()), \
             patch("app.get_levels", return_value=self._MOCK_LEVELS):
            resp = client.get("/api/levels/AAPL")
        data = resp.get_json()
        assert data["PDH"] == 500.0
        assert data["ORL"] == 493.0

    def test_error_returns_400(self, client):
        with patch("app.get_api", side_effect=Exception("API down")):
            resp = client.get("/api/levels/AAPL")
        assert resp.status_code == 400
        assert "error" in resp.get_json()


class TestApiVWAP:
    _MOCK_VWAP = [{"time": 1000, "value": 150.25}]

    def test_success_returns_200(self, client):
        with patch("app.get_api", return_value=MagicMock()), \
             patch("app.compute_vwap", return_value=self._MOCK_VWAP):
            resp = client.get("/api/vwap/AAPL")
        assert resp.status_code == 200

    def test_returns_vwap_data(self, client):
        with patch("app.get_api", return_value=MagicMock()), \
             patch("app.compute_vwap", return_value=self._MOCK_VWAP):
            resp = client.get("/api/vwap/AAPL")
        data = resp.get_json()
        assert data[0]["value"] == 150.25

    def test_error_returns_400(self, client):
        with patch("app.get_api", side_effect=Exception("no data")):
            resp = client.get("/api/vwap/AAPL")
        assert resp.status_code == 400

    def test_empty_vwap_returns_empty_list(self, client):
        with patch("app.get_api", return_value=MagicMock()), \
             patch("app.compute_vwap", return_value=[]):
            resp = client.get("/api/vwap/AAPL")
        assert resp.get_json() == []


class TestApiQuote:
    def _mock_requests_response(self, price, change_pct):
        mock_r = MagicMock()
        mock_r.raise_for_status.return_value = None
        mock_r.json.return_value = [{"price": price, "changePercentage": change_pct}]
        return mock_r

    def test_success_returns_200(self, client):
        with patch("requests.get", return_value=self._mock_requests_response(150.0, 1.5)):
            resp = client.get("/api/quote/AAPL")
        assert resp.status_code == 200

    def test_returns_price_and_change(self, client):
        with patch("requests.get", return_value=self._mock_requests_response(150.0, 1.5)):
            resp = client.get("/api/quote/AAPL")
        data = resp.get_json()
        assert data["price"] == 150.0
        assert data["changePercentage"] == 1.5

    def test_empty_response_returns_none_fields(self, client):
        mock_r = MagicMock()
        mock_r.raise_for_status.return_value = None
        mock_r.json.return_value = []
        with patch("requests.get", return_value=mock_r):
            resp = client.get("/api/quote/AAPL")
        data = resp.get_json()
        assert data["price"] is None
        assert data["changePercentage"] is None

    def test_network_error_returns_400(self, client):
        with patch("requests.get", side_effect=Exception("timeout")):
            resp = client.get("/api/quote/AAPL")
        assert resp.status_code == 400
        assert "error" in resp.get_json()
