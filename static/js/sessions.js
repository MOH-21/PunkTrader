/**
 * Sessions — market session backgrounds and vertical marker lines.
 *
 * Uses lightweight-charts Primitive API (v4.2+) to draw:
 * - Orange tint for pre-market  (01:00–06:29 ET)
 * - Blue tint for after-hours  (13:01–16:59 ET)
 * - White dotted lines at 01:00, 06:30, 13:00 ET
 *
 * Converts ET session times to chart's display-timezone automatically
 * using a hardcoded offset table for US timezones.
 */
(function() {

    /* ------------------------------------------------------------------ */
    /*  ET offset table (hours ET is ahead of display TZ)                 */
    /* ------------------------------------------------------------------ */

    var ET_OFFSETS = {
        "America/New_York":     0,
        "America/Detroit":      0,
        "America/Chicago":     -1,
        "America/Denver":      -2,
        "America/Boise":       -2,
        "America/Los_Angeles": -3,
        "America/Anchorage":   -4,
        "Pacific/Honolulu":    -5,
    };

    function _getETOffset() {
        var tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
        return ET_OFFSETS[tz] !== undefined ? ET_OFFSETS[tz] : 0;
    }

    /* ------------------------------------------------------------------ */
    /*  Session times (ET)                                                */
    /* ------------------------------------------------------------------ */

    var PREMARKET_START = { h: 1,  m: 0  };
    var MARKET_OPEN     = { h: 6,  m: 30 };
    var MARKET_CLOSE    = { h: 13, m: 0  };
    var AFTER_HOURS_END = { h: 16, m: 59 };

    var MARKER_TIMES = [
        { h: 1,  m: 0  },
        { h: 6,  m: 30 },
        { h: 13, m: 0  },
    ];

    /* ------------------------------------------------------------------ */
    /*  ET → chart-epoch conversion                                       */
    /* ------------------------------------------------------------------ */

    function _etToEpoch(dayStart, etHour, etMin, offsetH) {
        var localHour = etHour + offsetH;
        var d = dayStart;
        if (localHour < 0)   { localHour += 24; d -= 86400; }
        if (localHour >= 24) { localHour -= 24; d += 86400; }
        return d + localHour * 3600 + etMin * 60;
    }

    /* ------------------------------------------------------------------ */
    /*  Public API                                                        */
    /* ------------------------------------------------------------------ */

    function initSessionMarkers(panel) {
        if (!panel || !panel.candleSeries) return;
        var offsetH = _getETOffset();

        var primitive = {
            _chart: null,

            attached: function(params) {
                this._chart = params.chart;
            },

            renderer: function() {
                var self = this;
                return {
                    drawBackground: function(target) {
                        self._drawBg(target, self._chart);
                    },
                    draw: function(target) {
                        self._drawFg(target, self._chart);
                    },
                };
            },

            /* ---------------------------------------------------------- */
            /*  Background: semi-transparent session tints                 */
            /* ---------------------------------------------------------- */

            _drawBg: function(ctx, chart) {
                if (!chart || !ctx) return;
                var range = chart.timeScale().getVisibleRange();
                if (!range) return;

                var paneSize = chart.paneSize();
                var paneW = paneSize.width;
                var paneH = paneSize.height;
                if (paneW <= 0 || paneH <= 0) return;

                var fromDay = Math.floor(range.from / 86400) * 86400;
                var toDay   = Math.ceil(range.to / 86400)   * 86400;

                for (var day = fromDay; day <= toDay; day += 86400) {
                    // Pre-market: 01:00 ET → 06:29 ET
                    this._drawRect(ctx, chart,
                        _etToEpoch(day, PREMARKET_START.h, PREMARKET_START.m, offsetH),
                        _etToEpoch(day, MARKET_OPEN.h,     MARKET_OPEN.m,     offsetH) - 60,
                        paneW, paneH, "rgba(255,152,0,0.12)");

                    // After-hours: 13:01 ET → 16:59 ET
                    this._drawRect(ctx, chart,
                        _etToEpoch(day, MARKET_CLOSE.h,    MARKET_CLOSE.m + 1, offsetH),
                        _etToEpoch(day, AFTER_HOURS_END.h, AFTER_HOURS_END.m,  offsetH),
                        paneW, paneH, "rgba(41,98,255,0.12)");
                }
            },

            _drawRect: function(ctx, chart, t1, t2, paneW, paneH, color) {
                var x1 = chart.timeScale().timeToCoordinate(t1);
                var x2 = chart.timeScale().timeToCoordinate(t2);
                if (x1 === null || x2 === null) return;
                x1 = Math.max(0, Math.min(x1, paneW));
                x2 = Math.max(0, Math.min(x2, paneW));
                if (x2 <= x1) return;
                ctx.fillStyle = color;
                ctx.fillRect(x1, 0, x2 - x1, paneH);
            },

            /* ---------------------------------------------------------- */
            /*  Foreground: white dotted vertical lines                    */
            /* ---------------------------------------------------------- */

            _drawFg: function(ctx, chart) {
                if (!chart || !ctx) return;
                var range = chart.timeScale().getVisibleRange();
                if (!range) return;

                var paneSize = chart.paneSize();
                var paneW = paneSize.width;
                var paneH = paneSize.height;
                if (paneW <= 0 || paneH <= 0) return;

                var fromDay = Math.floor(range.from / 86400) * 86400;
                var toDay   = Math.ceil(range.to / 86400)   * 86400;

                ctx.save();
                ctx.setLineDash([4, 5]);
                ctx.strokeStyle = "rgba(255,255,255,0.45)";
                ctx.lineWidth = 1;

                for (var day = fromDay; day <= toDay; day += 86400) {
                    for (var i = 0; i < MARKER_TIMES.length; i++) {
                        var et = MARKER_TIMES[i];
                        var t = _etToEpoch(day, et.h, et.m, offsetH);
                        var x = chart.timeScale().timeToCoordinate(t);
                        if (x !== null && x >= 0 && x <= paneW) {
                            ctx.beginPath();
                            ctx.moveTo(x, 0);
                            ctx.lineTo(x, paneH);
                            ctx.stroke();
                        }
                    }
                }

                ctx.restore();
            },
        };

        panel.candleSeries.attachPrimitive(primitive);
        panel._sessionPrimitive = primitive;
    }

    function clearSessionMarkers(panel) {
        if (panel._sessionPrimitive && panel.candleSeries) {
            try { panel.candleSeries.detachPrimitive(panel._sessionPrimitive); } catch (e) {}
            panel._sessionPrimitive = null;
        }
    }

    window.initSessionMarkers = initSessionMarkers;
    window.clearSessionMarkers = clearSessionMarkers;

})();
