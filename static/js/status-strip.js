(function() {
  try {
    var strip = document.getElementById('status-strip');
    if (!strip) return;

    var tz = strip.dataset.timezone || 'America/Los_Angeles';

    var tzLabels = {
      'America/New_York': 'ET',
      'America/Chicago': 'CT',
      'America/Denver': 'MT',
      'America/Los_Angeles': 'PT',
    };
    var label = tzLabels[tz] || 'PT';

    // DST: second Sunday March (US) → first Sunday November
    function isUSDST(date) {
      var year = date.getUTCFullYear();
      // March 8 is always after the 2nd Sunday
      var dstStart = new Date(Date.UTC(year, 2, 8));
      while (dstStart.getUTCDay() !== 0) dstStart.setUTCDate(dstStart.getUTCDate() + 1);
      dstStart.setUTCHours(7); // 2AM ET = 7 UTC

      var dstEnd = new Date(Date.UTC(year, 10, 1));
      while (dstEnd.getUTCDay() !== 0) dstEnd.setUTCDate(dstEnd.getUTCDate() + 1);
      dstEnd.setUTCHours(6); // 2AM ET = 6 UTC (after fall-back)

      return date >= dstStart && date < dstEnd;
    }

    var stdOffsets = {
      'America/New_York': -300,    // EST: UTC-5
      'America/Chicago': -360,     // CST: UTC-6
      'America/Denver': -420,      // MST: UTC-7
      'America/Los_Angeles': -480, // PST: UTC-8
    };
    var dstOffsets = {
      'America/New_York': -240,    // EDT: UTC-4
      'America/Chicago': -300,     // CDT: UTC-5
      'America/Denver': -360,      // MDT: UTC-6
      'America/Los_Angeles': -420, // PDT: UTC-7
    };

    function tzOffset(tz, now) {
      var base = stdOffsets[tz] !== undefined ? stdOffsets[tz] : -new Date().getTimezoneOffset();
      if (isUSDST(now)) {
        var dst = dstOffsets[tz];
        if (dst !== undefined) return dst;
      }
      return base;
    }

    function getTimeInTZ(tz) {
      var now = new Date();
      var offset = tzOffset(tz, now);
      var utc = now.getTime() + now.getTimezoneOffset() * 60000;
      var tzTime = new Date(utc + offset * 60000);
      return { h: tzTime.getUTCHours(), m: tzTime.getUTCMinutes(), s: tzTime.getUTCSeconds() };
    }

    function getActiveSession() {
      var et = getTimeInTZ('America/New_York');
      var etHour = et.h + et.m / 60;
      if (etHour >= 4 && etHour < 9.5) return 'PRE';
      if (etHour >= 9.5 && etHour < 16) return 'RTH';
      if (etHour >= 16 && etHour < 20) return 'AH';
      return 'CLOSED';
    }

    function fmt(n) { return n < 10 ? '0' + n : '' + n; }

    function update() {
      try {
        var t = getTimeInTZ(tz);
        var session = getActiveSession();
        var cls = function(s) { return session === s ? 'session-active' : 'session-dim'; };
        strip.innerHTML =
          'MKT  ' + fmt(t.h) + ':' + fmt(t.m) + ':' + fmt(t.s) + ' ' + label + '  •  ' +
          '<span class="' + cls('PRE') + '">PRE</span>  ' +
          '<span class="' + cls('RTH') + '">RTH</span>  ' +
          '<span class="' + cls('AH') + '">AH</span>';
      } catch (e) {}
    }

    update();
    setInterval(update, 1000);
  } catch (e) {
    console.error('Status strip error:', e);
  }
})();
