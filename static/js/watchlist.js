(function() {
  var sidebar = document.querySelector('#sidebar');
  var watchlistList = document.querySelector('.watchlist-list');
  var tickersStr = sidebar && sidebar.dataset.watchlist ? sidebar.dataset.watchlist : '';
  var configTickers = tickersStr.split(',').filter(function(t) { return t.trim(); });

  // Merge config tickers with user-added tickers from localStorage
  function _extraKey() {
    var k = 'pt_watchlist_extra';
    if (window.ptKey) { var n = window.ptKey('watchlist_extra'); if (n) k = n; }
    return k;
  }

  function loadExtraTickers() {
    try { var v = localStorage.getItem(_extraKey()); if (v) return v.split(',').filter(function(t) { return t.trim(); }); } catch (e) {}
    return [];
  }

  function saveExtraTickers(extra) {
    try { localStorage.setItem(_extraKey(), extra.join(',')); } catch (e) {}
  }

  var extraTickers = loadExtraTickers();
  var allTickers = configTickers.concat(extraTickers).filter(function(t, i, a) { return a.indexOf(t) === i; }); // dedupe
  var tickerRows = new Map();
  var lastTickTimestamp = new Map();
  var stalennessInterval;

  function renderRows() {
    allTickers.forEach(function(ticker) {
      _createRow(ticker);
    });
    _renderAddInput();
  }

  function _createRow(ticker) {
    var row = document.createElement('div');
    row.className = 'watchlist-row';
    row.dataset.ticker = ticker;

    var slab = document.createElement('div');
    slab.className = 'wl-slab';
    row.appendChild(slab);

    var tickerDiv = document.createElement('div');
    tickerDiv.className = 'wl-ticker';
    tickerDiv.textContent = ticker;
    row.appendChild(tickerDiv);

    var pricesDiv = document.createElement('div');
    pricesDiv.className = 'wl-prices';

    var priceEl = document.createElement('div');
    priceEl.className = 'wl-price';
    priceEl.textContent = '--';
    pricesDiv.appendChild(priceEl);

    var changeEl = document.createElement('div');
    changeEl.className = 'wl-change';
    changeEl.textContent = '--';
    pricesDiv.appendChild(changeEl);

    row.appendChild(pricesDiv);

    // Remove button — only for user-added (non-config) tickers
    if (configTickers.indexOf(ticker) === -1) {
      var removeBtn = document.createElement('span');
      removeBtn.className = 'wl-remove';
      removeBtn.textContent = '×';
      removeBtn.title = 'Remove from watchlist';
      removeBtn.addEventListener('click', function(e) {
        e.stopPropagation();
        removeTicker(ticker);
      });
      row.appendChild(removeBtn);
    }

    row.addEventListener('click', handleRowClick);
    watchlistList.appendChild(row);
    tickerRows.set(ticker, row);
    lastTickTimestamp.set(ticker, Date.now());
  }

  function _renderAddInput() {
    var wrapper = document.createElement('div');
    wrapper.className = 'wl-add-wrapper';

    var input = document.createElement('input');
    input.type = 'text';
    input.className = 'wl-add-input';
    input.placeholder = '+ ADD TICKER';
    input.spellcheck = false;
    input.autocomplete = 'off';

    input.addEventListener('keydown', function(e) {
      if (e.key === 'Enter') {
        var raw = input.value.trim().toUpperCase();
        var clean = raw.replace(/[^A-Z]/g, '');
        if (clean.length > 10) clean = clean.slice(0, 10);
        if (clean) {
          addTicker(clean);
        }
        input.value = '';
      }
    });

    wrapper.appendChild(input);
    watchlistList.appendChild(wrapper);
  }

  function addTicker(ticker) {
    if (tickerRows.has(ticker)) return;
    allTickers.push(ticker);
    extraTickers.push(ticker);
    saveExtraTickers(extraTickers);
    _createRow(ticker);
    // Subscribe backend + get initial quote
    fetch('/api/watchlist/add/' + ticker)
      .then(function(res) { return res.json(); })
      .then(function(data) {
        if (data.error || data.price === null || data.price === undefined) {
          removeTicker(ticker);
          return;
        }
        _updateRowPrice(ticker, data);
      })
      .catch(function(err) {
        console.error('Failed to add ticker ' + ticker + ':', err);
        removeTicker(ticker);
      });
  }

  function removeTicker(ticker) {
    if (configTickers.indexOf(ticker) !== -1) return; // can't remove config tickers
    var row = tickerRows.get(ticker);
    if (row) row.remove();
    tickerRows.delete(ticker);
    lastTickTimestamp.delete(ticker);
    allTickers = allTickers.filter(function(t) { return t !== ticker; });
    extraTickers = extraTickers.filter(function(t) { return t !== ticker; });
    saveExtraTickers(extraTickers);
    // Unsubscribe backend
    fetch('/api/watchlist/remove/' + ticker).catch(function() {});
  }

  function _updateRowPrice(ticker, data) {
    var row = tickerRows.get(ticker);
    if (!row) return;
    if (data.price !== undefined && data.price !== null) {
      var priceEl = row.querySelector('.wl-price');
      if (priceEl) priceEl.textContent = data.price.toFixed(2);
      var changeEl = row.querySelector('.wl-change');
      if (changeEl && data.changePercentage !== undefined) {
        var pct = data.changePercentage;
        changeEl.textContent = (pct >= 0 ? '+' : '') + pct.toFixed(2) + '%';
        changeEl.className = 'wl-change ' + (pct >= 0 ? 'up' : 'down');
      }
    }
  }

  function fetchQuote(ticker) {
    fetch('/api/quote/' + ticker)
      .then(function(res) { return res.json(); })
      .then(function(data) {
        _updateRowPrice(ticker, data);
      })
      .catch(function(err) { console.error('Failed to fetch quote for ' + ticker + ':', err); });
  }

  function fetchInitialPrices() {
    allTickers.forEach(function(ticker) {
      fetchQuote(ticker);
    });
  }

  function syncExtraTickers() {
    if (extraTickers.length === 0) return;
    fetch('/api/watchlist/sync', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tickers: extraTickers }),
    }).catch(function() {});
  }

  function handleRowClick(evt) {
    var row = evt.currentTarget;
    var ticker = row.dataset.ticker;
    row.classList.add('flash');
    setTimeout(function() { row.classList.remove('flash'); }, 80);
    if (!window.layoutManager) return;
    window.layoutManager.setTicker(ticker);
    var tickerInput = document.getElementById('ticker-input');
    if (tickerInput) tickerInput.value = ticker;
    var key = 'pt_ticker';
    if (window.ptKey) key = window.ptKey('ticker');
    try { localStorage.setItem(key, ticker); } catch (e) {}
  }

  function subscribeToUpdates() {
    var eventSource = new EventSource('/stream/watchlist');
    eventSource.addEventListener('price', function(evt) {
      var data = JSON.parse(evt.data);
      var ticker = data.ticker;
      var price = data.price;
      var row = tickerRows.get(ticker);
      if (row) {
        var priceEl = row.querySelector('.wl-price');
        if (priceEl) priceEl.textContent = price.toFixed(2);
        lastTickTimestamp.set(ticker, Date.now());
        row.classList.add('tick');
        setTimeout(function() { row.classList.remove('tick'); }, 250);
      }
    });
  }

  function monitorStaleness() {
    stalennessInterval = setInterval(function() {
      var now = Date.now();
      allTickers.forEach(function(ticker) {
        var row = tickerRows.get(ticker);
        if (!row) return;
        var lastTick = lastTickTimestamp.get(ticker);
        var elapsed = now - lastTick;
        row.classList.toggle('stale', elapsed > 10000);
      });
    }, 5000);
  }

  function setActiveFromLocalStorage() {
    var key = 'pt_ticker';
    if (window.ptKey) key = window.ptKey('ticker');
    var savedTicker = null;
    try { savedTicker = localStorage.getItem(key); } catch (e) {}
    if (savedTicker && tickerRows.has(savedTicker)) {
      var row = tickerRows.get(savedTicker);
      row.classList.add('active');
    }
  }

  function listenToActivePanelChanges() {
    document.addEventListener('pt:active-panel-changed', function(evt) {
      var newTicker = evt.detail.ticker;
      tickerRows.forEach(function(row, ticker) {
        row.classList.toggle('active', ticker === newTicker);
      });
    });
  }

  function init() {
    if (!sidebar || !watchlistList) return;
    syncExtraTickers();
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
