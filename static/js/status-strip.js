function getETOffset() {
  const now = new Date();
  const utcDate = new Date(now.getTime() + now.getTimezoneOffset() * 60000);
  const etDate = new Date(utcDate.getTime() - 5 * 3600000);

  const january = new Date(now.getFullYear(), 0, 1);
  const july = new Date(now.getFullYear(), 6, 1);

  const janOffset = Math.round((january.getTime() - Date.UTC(january.getFullYear(), 0, 1)) / 3600000);
  const julOffset = Math.round((july.getTime() - Date.UTC(july.getFullYear(), 6, 1)) / 3600000);

  const dst = janOffset === julOffset ? false : now.getTimezoneOffset() < Math.max(janOffset, julOffset);

  return dst ? -4 : -5;
}

function getETTime() {
  const now = new Date();
  const offset = getETOffset();
  const etTime = new Date(now.getTime() + (offset * 3600000) - (now.getTimezoneOffset() * 60000));
  return etTime;
}

function getActiveSession(etHour) {
  if (etHour >= 4 && etHour < 9.5) return 'PRE';
  if (etHour >= 9.5 && etHour < 16) return 'RTH';
  if (etHour >= 16 && etHour < 20) return 'AH';
  return 'CLOSED';
}

function formatTime(date) {
  const h = String(date.getHours()).padStart(2, '0');
  const m = String(date.getMinutes()).padStart(2, '0');
  const s = String(date.getSeconds()).padStart(2, '0');
  return `${h}:${m}:${s}`;
}

function update() {
  const strip = document.getElementById('status-strip');
  if (!strip) return;

  const etTime = getETTime();
  const timeStr = formatTime(etTime);
  const etHour = etTime.getHours() + etTime.getMinutes() / 60;
  const activeSession = getActiveSession(etHour);

  const preClass = activeSession === 'PRE' ? 'session-active' : 'session-dim';
  const rthClass = activeSession === 'RTH' ? 'session-active' : 'session-dim';
  const ahClass = activeSession === 'AH' ? 'session-active' : 'session-dim';

  strip.innerHTML = `MKT  ${timeStr} ET  •  <span class="${preClass}">PRE</span>  <span class="${rthClass}">RTH</span>  <span class="${ahClass}">AH</span>`;
}

update();
setInterval(update, 1000);
