import pytest
from levels.alerts import (
    AlertState, analyze_price_action, evaluate_bar, check_proximity,
    MAX_ALERTS_PER_LEVEL,
)


class TestAnalyzePriceAction:
    def test_zero_range_is_indecision(self):
        label, detail = analyze_price_action(100, 100, 100, 100)
        assert label == "INDECISION"
        assert detail is None

    def test_tiny_body_is_indecision(self):
        # body=0.01, range=1.0 → body < 5% of range
        label, detail = analyze_price_action(100.0, 100.5, 99.5, 100.01)
        assert label == "INDECISION"

    def test_strong_green_no_wick(self):
        # open=100, close=102, high=102, low=100 — clean green, no wicks
        label, detail = analyze_price_action(100, 102, 100, 102)
        assert label == "STRONG"
        assert detail is None

    def test_strong_green_buyer_wick(self):
        # open=100, close=104, high=104, low=98
        # lower_wick = 100-98 = 2, range=6, threshold=1.5 → notable
        label, detail = analyze_price_action(100, 104, 98, 104)
        assert label == "STRONG"
        assert detail == "buyer wick"

    def test_weak_red_no_wick(self):
        # open=102, close=100, high=102, low=100 — clean red, no wicks
        label, detail = analyze_price_action(102, 102, 100, 100)
        assert label == "WEAK"
        assert detail is None

    def test_weak_red_seller_wick(self):
        # open=104, close=100, high=106, low=100
        # upper_wick = 106-104 = 2, range=6, threshold=1.5 → notable
        label, detail = analyze_price_action(104, 106, 100, 100)
        assert label == "WEAK"
        assert detail == "seller wick"


class TestEvaluateBar:
    def _bar(self, close, level=500.0):
        """Minimal bar: close relative to level."""
        return dict(ticker="SPY", level_name="PDH", level_price=level,
                    candle_open=close - 1, candle_high=close + 1,
                    candle_low=close - 2, candle_close=close)

    def test_none_level_price_returns_none(self):
        state = AlertState()
        result = evaluate_bar("SPY", "PDH", None, 498, 502, 497, 499, state, 1000)
        assert result is None

    def test_first_call_initializes_side_below(self):
        state = AlertState()
        result = evaluate_bar("SPY", "PDH", 500.0, 498, 502, 497, 499, state, 1000)
        assert result is None
        assert state.side == "below"

    def test_first_call_initializes_side_above(self):
        state = AlertState()
        result = evaluate_bar("SPY", "PDH", 500.0, 501, 503, 500, 501, state, 1000)
        assert result is None
        assert state.side == "above"

    def test_same_side_returns_none(self):
        state = AlertState()
        evaluate_bar("SPY", "PDH", 500.0, 498, 502, 497, 499, state, 1000)
        result = evaluate_bar("SPY", "PDH", 500.0, 498, 502, 497, 499.5, state, 1060)
        assert result is None

    def test_break_above(self):
        state = AlertState()
        evaluate_bar("SPY", "PDH", 500.0, 498, 502, 497, 499, state, 1000)
        result = evaluate_bar("SPY", "PDH", 500.0, 500, 503, 499, 501, state, 1060)
        assert result is not None
        assert result["event"] == "BREAK ABOVE"
        assert result["kind"] == "break_above"
        assert result["ticker"] == "SPY"
        assert result["level"] == "PDH"
        assert result["level_price"] == 500.0
        assert result["close"] == 501
        assert state.has_broken is True

    def test_break_below(self):
        state = AlertState()
        evaluate_bar("SPY", "PDH", 500.0, 501, 503, 500, 501, state, 1000)
        result = evaluate_bar("SPY", "PDH", 500.0, 499, 500, 498, 499, state, 1060)
        assert result["event"] == "BREAK BELOW"
        assert result["kind"] == "break_below"

    def test_fade_after_break_above(self):
        # break above → then close below → FADE
        state = AlertState()
        evaluate_bar("SPY", "PDH", 500.0, 498, 502, 497, 499, state, 900)   # side=below
        evaluate_bar("SPY", "PDH", 500.0, 500, 503, 499, 501, state, 960)   # BREAK ABOVE
        result = evaluate_bar("SPY", "PDH", 500.0, 501, 502, 498, 499, state, 1020)
        assert result["event"] == "FADE"
        assert result["kind"] == "fade"

    def test_reclaim_after_break_below(self):
        # break below → then close above → RECLAIM
        state = AlertState()
        evaluate_bar("SPY", "PDH", 500.0, 501, 503, 500, 501, state, 900)  # side=above
        evaluate_bar("SPY", "PDH", 500.0, 500, 501, 498, 499, state, 960)  # BREAK BELOW
        result = evaluate_bar("SPY", "PDH", 500.0, 499, 502, 498, 501, state, 1020)
        assert result["event"] == "RECLAIM"
        assert result["kind"] == "reclaim"

    def test_max_alerts_caps_after_three_crosses(self):
        state = AlertState()
        evaluate_bar("SPY", "PDH", 500.0, 498, 502, 497, 499, state, 900)  # init below
        crosses = [501, 499, 501]  # 3 crosses: above, below, above
        fired = []
        for i, close in enumerate(crosses):
            r = evaluate_bar("SPY", "PDH", 500.0, close-1, close+1, close-2, close, state, 1000+i*60)
            fired.append(r)
        assert all(r is not None for r in fired)
        assert state.cross_count == MAX_ALERTS_PER_LEVEL
        # 4th cross: capped
        result = evaluate_bar("SPY", "PDH", 500.0, 498, 502, 497, 499, state, 4000)
        assert result is None

    def test_result_contains_pa_fields(self):
        state = AlertState()
        evaluate_bar("SPY", "PDH", 500.0, 498, 502, 497, 499, state, 900)
        result = evaluate_bar("SPY", "PDH", 500.0, 500, 503, 499, 501, state, 960)
        assert "pa_label" in result
        assert "pa_detail" in result
        assert "text" in result
        assert "time" in result

    def test_timestamp_used_when_provided(self):
        state = AlertState()
        evaluate_bar("SPY", "PDH", 500.0, 498, 502, 497, 499, state, 900)
        result = evaluate_bar("SPY", "PDH", 500.0, 500, 503, 499, 501, state, 99999)
        assert result["time"] == 99999


class TestCheckProximity:
    def _state_with_side(self, side="below"):
        s = AlertState()
        s.side = side
        return s

    def test_within_threshold_fires(self):
        state = self._state_with_side("below")
        # 500 * 0.001 = 0.5 → 499.6 is 0.08% away
        result = check_proximity("SPY", "PDH", 500.0, 499.6, state, 1000)
        assert result is not None
        assert result["event"] == "PROXIMITY"
        assert result["kind"] == "proximity"
        assert state.proximity_fired is True

    def test_outside_threshold_no_fire(self):
        state = self._state_with_side("below")
        # 495.0 is 1% away
        result = check_proximity("SPY", "PDH", 500.0, 495.0, state, 1000)
        assert result is None

    def test_exact_match_no_fire(self):
        # distance_pct == 0, condition requires > 0
        state = self._state_with_side("above")
        result = check_proximity("SPY", "PDH", 500.0, 500.0, state, 1000)
        assert result is None

    def test_already_fired_no_repeat(self):
        state = self._state_with_side("below")
        state.proximity_fired = True
        result = check_proximity("SPY", "PDH", 500.0, 499.6, state, 1000)
        assert result is None

    def test_already_broken_no_fire(self):
        state = self._state_with_side("below")
        state.has_broken = True
        result = check_proximity("SPY", "PDH", 500.0, 499.6, state, 1000)
        assert result is None

    def test_side_none_no_fire(self):
        state = AlertState()
        result = check_proximity("SPY", "PDH", 500.0, 499.6, state, 1000)
        assert result is None

    def test_none_level_price_no_fire(self):
        state = self._state_with_side("below")
        result = check_proximity("SPY", "PDH", None, 499.6, state, 1000)
        assert result is None

    def test_fires_from_above(self):
        state = self._state_with_side("above")
        # 500.6 is 0.12% above 500
        result = check_proximity("SPY", "PDH", 500.0, 500.6, state, 1000)
        assert result is not None
        assert "from above" in result["text"]

    def test_fires_from_below(self):
        state = self._state_with_side("below")
        result = check_proximity("SPY", "PDH", 500.0, 499.6, state, 1000)
        assert result is not None
        assert "from below" in result["text"]

    def test_result_fields_complete(self):
        state = self._state_with_side("below")
        result = check_proximity("SPY", "PDH", 500.0, 499.6, state, 12345)
        assert result["ticker"] == "SPY"
        assert result["level"] == "PDH"
        assert result["level_price"] == 500.0
        assert result["close"] == 499.6
        assert result["time"] == 12345
