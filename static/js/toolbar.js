/**
 * Toolbar — wires up ticker input, timeframe buttons, and layout buttons.
 */
function initToolbar(layoutManager, ptKey) {
    try {
        const tickerInput = document.getElementById('ticker-input');
        const tfButtons = document.querySelectorAll('.tf-btn');
        const layoutButtons = document.querySelectorAll('.layout-btn');

        // Fallback if ptKey not provided (direct load without ?i=)
        if (!ptKey) ptKey = function(name) { return 'pt_' + name; };

        // --- Sidebar toggle ---
        const sidebarToggle = document.getElementById('sidebar-toggle');
        const appShell = document.getElementById('app-shell');

        var sidebarCollapsed = false;
        try { sidebarCollapsed = localStorage.getItem(ptKey('sidebar')) === 'collapsed'; } catch (e) {}
        if (sidebarCollapsed && appShell) {
            appShell.classList.add('sidebar-collapsed');
            if (sidebarToggle) sidebarToggle.textContent = '▶';
        }

        if (sidebarToggle && appShell) {
            sidebarToggle.addEventListener('click', function() {
                sidebarCollapsed = !sidebarCollapsed;
                appShell.classList.toggle('sidebar-collapsed', sidebarCollapsed);
                sidebarToggle.textContent = sidebarCollapsed ? '▶' : '◀';
                try { localStorage.setItem(ptKey('sidebar'), sidebarCollapsed ? 'collapsed' : 'expanded'); } catch (e) {}
            });
        }

        // --- Ticker input ---
        if (tickerInput) {
            tickerInput.addEventListener('input', function() {
                var pos = tickerInput.selectionStart;
                tickerInput.value = tickerInput.value.toUpperCase();
                tickerInput.setSelectionRange(pos, pos);
            });

            tickerInput.addEventListener('keydown', function(e) {
                if (e.key === 'Enter') {
                    var raw = tickerInput.value.trim().toUpperCase();
                    var clean = raw.replace(/[^A-Z]/g, '');
                    if (clean.length > 10) clean = clean.slice(0, 10);
                    if (clean && layoutManager) {
                        layoutManager.setTicker(clean);
                        tickerInput.value = clean;
                        try { localStorage.setItem(ptKey('ticker'), clean); } catch (ex) {}
                    }
                    tickerInput.blur();
                }
            });

            tickerInput.addEventListener('focus', function() { tickerInput.select(); });
        }

        // --- Timeframe buttons ---
        if (tfButtons && tfButtons.length > 0) {
            Array.prototype.forEach.call(tfButtons, function(btn) {
                btn.addEventListener('click', function() {
                    Array.prototype.forEach.call(tfButtons, function(b) { b.classList.remove('active'); });
                    btn.classList.add('active');
                    var tf = btn.dataset.tf;
                    if (layoutManager) layoutManager.setTimeframe(tf);
                    try { localStorage.setItem(ptKey('timeframe'), tf); } catch (e) {}
                });
            });
        }

        // Restore saved timeframe
        var savedTf = null;
        try { savedTf = localStorage.getItem(ptKey('timeframe')); } catch (e) {}
        if (savedTf && tfButtons) {
            Array.prototype.forEach.call(tfButtons, function(b) {
                b.classList.toggle('active', b.dataset.tf === savedTf);
            });
        }

        // --- Layout buttons ---
        if (layoutButtons && layoutButtons.length > 0) {
            Array.prototype.forEach.call(layoutButtons, function(btn) {
                btn.addEventListener('click', function() {
                    Array.prototype.forEach.call(layoutButtons, function(b) { b.classList.remove('active'); });
                    btn.classList.add('active');
                    var layout = btn.dataset.layout;
                    if (layoutManager) layoutManager.setLayout(layout);
                    try { localStorage.setItem(ptKey('layout'), layout); } catch (e) {}
                });
            });
        }

        // Restore saved layout
        var savedLayout = null;
        try { savedLayout = localStorage.getItem(ptKey('layout')); } catch (e) {}
        if (savedLayout && layoutButtons) {
            Array.prototype.forEach.call(layoutButtons, function(b) {
                b.classList.toggle('active', b.dataset.layout === savedLayout);
            });
        }

        // --- Draw tool toggle ---
        var drawToggle = document.getElementById('draw-toggle');
        if (drawToggle && typeof setDrawToolActive === 'function') {
            drawToggle.addEventListener('click', function () {
                var active = !drawToggle.classList.contains('active');
                drawToggle.classList.toggle('active', active);
                setDrawToolActive(active);
            });
            // Deactivate on layout change (lines get destroyed on panel recreate)
            if (layoutButtons) {
                Array.prototype.forEach.call(layoutButtons, function(btn) {
                    btn.addEventListener('click', function () {
                        if (drawToggle.classList.contains('active')) {
                            drawToggle.classList.remove('active');
                            setDrawToolActive(false);
                        }
                    });
                });
            }
        }

        return { savedTf: savedTf, savedLayout: savedLayout };
    } catch (e) {
        console.error('Toolbar init failed:', e);
        return { savedTf: null, savedLayout: null };
    }
}
