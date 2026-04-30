(function() {
  const sidebar = document.querySelector('#sidebar');
  const watchlistList = document.querySelector('.watchlist-list');
  const tickersStr = sidebar?.dataset.watchlist || '';
  const tickers = tickersStr.split(',').filter(t => t.trim());
  const tickerRows = new Map();
  const lastTickTimestamp = new Map();
  let stalennessInterval;

  function renderRows() {
    tickers.forEach(ticker => {
      const row = document.createElement('div');
      row.className = 'watchlist-row';
      row.dataset.ticker = ticker;
      row.innerHTML = `
        <div class="wl-slab"></div>
        <div class="wl-prices">
          <div class="wl-price">--</div>
          <div class="wl-change">--</div>
        </div>
      `;
      const tickerDiv = document.createElement('div');
      tickerDiv.className = 'wl-ticker';
      tickerDiv.textContent = ticker;
      row.insertBefore(tickerDiv, row.querySelector('.wl-prices'));
      row.addEventListener('click', handleRowClick);
      watchlistList.appendChild(row);
      tickerRows.set(ticker, row);
      lastTickTimestamp.set(ticker, Date.now());
    });
  }

  function fetchInitialPrices() {
    tickers.forEach(ticker => {
      fetch(`/api/quote/${ticker}`)
        .then(res => res.json())
        .then(data => {
          const row = tickerRows.get(ticker);
          if (row) {
            const priceEl = row.querySelector('.wl-price');
            const changeEl = row.querySelector('.wl-change');
            priceEl.textContent = data.price.toFixed(2);
            const pct = data.changePercentage;
            changeEl.textContent = (pct >= 0 ? '+' : '') + pct.toFixed(2) + '%';
            changeEl.className = 'wl-change ' + (pct >= 0 ? 'up' : 'down');
          }
        })
        .catch(err => console.error(`Failed to fetch quote for ${ticker}:`, err));
    });
  }

  function handleRowClick(evt) {
    const row = evt.currentTarget;
    const ticker = row.dataset.ticker;
    row.classList.add('flash');
    setTimeout(() => row.classList.remove('flash'), 80);
    if (!window.layoutManager) return;
    window.layoutManager.setTicker(ticker);
    const tickerInput = document.getElementById('ticker-input');
    if (tickerInput) tickerInput.value = ticker;
    const ptKey = window.ptKey || function(n) { return 'pt_' + n; };
    localStorage.setItem(ptKey('ticker'), ticker);
  }

  function subscribeToUpdates() {
    const eventSource = new EventSource('/stream/watchlist');
    eventSource.addEventListener('price', (evt) => {
      const data = JSON.parse(evt.data);
      const ticker = data.ticker;
      const price = data.price;
      const row = tickerRows.get(ticker);
      if (row) {
        const priceEl = row.querySelector('.wl-price');
        priceEl.textContent = price.toFixed(2);
        lastTickTimestamp.set(ticker, Date.now());
        row.classList.add('tick');
        setTimeout(() => row.classList.remove('tick'), 250);
      }
    });
  }

  function monitorStaleness() {
    stalennessInterval = setInterval(() => {
      const now = Date.now();
      tickers.forEach(ticker => {
        const row = tickerRows.get(ticker);
        const lastTick = lastTickTimestamp.get(ticker);
        const elapsed = now - lastTick;
        if (elapsed > 10000) {
          row.classList.add('stale');
        } else {
          row.classList.remove('stale');
        }
      });
    }, 5000);
  }

  function setActiveFromLocalStorage() {
    const ptKey = window.ptKey || function(n) { return 'pt_' + n; };
    const savedTicker = localStorage.getItem(ptKey('ticker'));
    if (savedTicker && tickerRows.has(savedTicker)) {
      const row = tickerRows.get(savedTicker);
      row.classList.add('active');
    }
  }

  function listenToActivePanelChanges() {
    document.addEventListener('pt:active-panel-changed', (evt) => {
      const newTicker = evt.detail.ticker;
      tickerRows.forEach((row, ticker) => {
        if (ticker === newTicker) {
          row.classList.add('active');
        } else {
          row.classList.remove('active');
        }
      });
    });
  }

  function init() {
    if (!sidebar || !watchlistList) return;
    renderRows();
    fetchInitialPrices();
    subscribeToUpdates();
    monitorStaleness();
    setActiveFromLocalStorage();
    listenToActivePanelChanges();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
