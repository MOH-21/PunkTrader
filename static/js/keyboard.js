const timeframeMap = {
  '1': '1Min',
  '2': '5Min',
  '3': '15Min',
  '4': '1Hour',
  '5': '4Hour',
  '6': '1Day',
  '7': '1Week'
};

const layoutCycle = ['1x1', '1x2', '2x2'];

let tickerInputPreviousValue = '';

const tickerInput = document.getElementById('ticker-input');
if (tickerInput) {
  tickerInput.addEventListener('focus', () => {
    tickerInputPreviousValue = tickerInput.value;
  });
}

document.addEventListener('keydown', (e) => {
  const target = e.target;
  const isInput = target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.tagName === 'SELECT' || target.hasAttribute('contenteditable');
  const isTickerInput = target.id === 'ticker-input';

  if (isInput && !isTickerInput) {
    return;
  }

  if (isTickerInput) {
    if (e.key === 'Escape') {
      e.preventDefault();
      tickerInput.blur();
      tickerInput.value = tickerInputPreviousValue;
      return;
    }
    if (e.key === 'Enter') {
      e.preventDefault();
      if (typeof layoutManager !== 'undefined' && layoutManager.setTicker) {
        layoutManager.setTicker(tickerInput.value.trim().toUpperCase());
      }
      return;
    }
  }

  if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
    e.preventDefault();
    if (tickerInput) {
      tickerInput.focus();
      tickerInput.select();
    }
    return;
  }

  if (e.key === '/' && !e.ctrlKey && !e.metaKey && !e.shiftKey && !e.altKey) {
    e.preventDefault();
    if (tickerInput) {
      tickerInput.focus();
      tickerInput.value = '';
    }
    return;
  }

  if (isTickerInput && e.key === 'L' && !e.ctrlKey && !e.metaKey && !e.altKey) {
    return; // Let L through when typing in ticker input
  }

  if (e.shiftKey && e.key === 'L' && !e.ctrlKey && !e.metaKey && !e.altKey) {
    e.preventDefault();
    if (typeof layoutManager !== 'undefined') {
      const currentLayout = layoutManager.currentLayout;
      const currentIndex = layoutCycle.indexOf(currentLayout);
      const nextIndex = (currentIndex + 1) % layoutCycle.length;
      const nextLayout = layoutCycle[nextIndex];
      layoutManager.setLayout(nextLayout);
      const chartGrid = document.getElementById('chart-grid');
      if (chartGrid) {
        chartGrid.classList.add('layout-flash');
        setTimeout(() => {
          chartGrid.classList.remove('layout-flash');
        }, 100);
      }
    }
    return;
  }

  if (!e.ctrlKey && !e.metaKey && !e.shiftKey && !e.altKey && e.key >= '1' && e.key <= '7' && !isTickerInput) {
    e.preventDefault();
    const tf = timeframeMap[e.key];
    if (typeof layoutManager !== 'undefined' && layoutManager.setTimeframe) {
      layoutManager.setTimeframe(tf);
    }
    return;
  }

  if (!e.ctrlKey && !e.metaKey && !e.shiftKey && !e.altKey && e.key.length === 1 && /^[a-z]$/i.test(e.key)) {
    if (tickerInput && document.activeElement !== tickerInput) {
      tickerInput.focus();
      tickerInput.value = '';
      tickerInput.classList.add('flash');
      setTimeout(function() {
        tickerInput.classList.remove('flash');
      }, 120);
    }
    // Don't preventDefault — let the native character flow into the focused input
    return;
  }
});
