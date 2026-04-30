/**
 * DrawTool — horizontal line drawing tool for ChartPanel.
 *
 * Toggle via setDrawToolActive(). When active, clicking on chart
 * places a horizontal priceLine. Clicking near an existing line
 * opens a color picker popup.
 */
(function () {
  var DEFAULT_COLOR = '#FFFFFF';
  var LINE_WIDTH = 2;
  var PRICE_TOLERANCE = 0.0005;

  var _globalActive = false;

  function initDrawTool(panel) {
    panel._drawLines = panel._drawLines || [];
    panel._drawPopup = null;

    panel.chart.subscribeClick(function (param) {
      if (!_globalActive) return;
      if (!param.point || param.time === undefined) return;

      var price = panel.candleSeries.coordinateToPrice(param.point.y);
      if (price === null || price === undefined) return;

      var rounded = Math.round(price * 100) / 100;

      // Check if clicking near existing line
      var existing = null;
      for (var i = 0; i < panel._drawLines.length; i++) {
        var dl = panel._drawLines[i];
        var diff = Math.abs(dl.price - rounded) / Math.max(Math.abs(dl.price), 0.01);
        if (diff < PRICE_TOLERANCE) {
          existing = dl;
          break;
        }
      }

      if (existing) {
        _showSettings(panel, existing, param.point);
        return;
      }

      // Create new line
      _createLine(panel, rounded, DEFAULT_COLOR);
    });
  }

  function _createLine(panel, price, color) {
    // Replace any line at exact same price
    for (var i = 0; i < panel._drawLines.length; i++) {
      if (panel._drawLines[i].price === price) {
        try { panel.candleSeries.removePriceLine(panel._drawLines[i].priceLine); } catch (e) {}
        panel._drawLines.splice(i, 1);
        break;
      }
    }

    var priceLine = panel.candleSeries.createPriceLine({
      price: price,
      color: color,
      lineWidth: LINE_WIDTH,
      lineStyle: 0,
      axisLabelVisible: false,
      title: '',
    });

    panel._drawLines.push({ price: price, color: color, priceLine: priceLine });
  }

  function _showSettings(panel, drawLine, point) {
    _closePopup(panel);

    var container = panel.container;
    var rect = container.getBoundingClientRect();
    var left = point.x + 15;
    var top = point.y - 50;
    if (left + 200 > rect.width) left = Math.max(0, point.x - 215);
    if (top < 10) top = point.y + 15;

    var popup = document.createElement('div');
    popup.className = 'draw-line-popup';
    popup.style.cssText = 'left:' + left + 'px;top:' + top + 'px;';

    popup.innerHTML =
      '<div class="dl-popup-inner">' +
        '<span class="dl-popup-label">Color</span>' +
        '<input type="color" class="dl-color-input" value="' + drawLine.color + '">' +
        '<button class="dl-delete-btn">Delete</button>' +
      '</div>';

    // Color change
    var colorInput = popup.querySelector('.dl-color-input');
    colorInput.addEventListener('input', function () {
      drawLine.color = colorInput.value;
      try {
        panel.candleSeries.removePriceLine(drawLine.priceLine);
        drawLine.priceLine = panel.candleSeries.createPriceLine({
          price: drawLine.price,
          color: drawLine.color,
          lineWidth: LINE_WIDTH,
          lineStyle: 0,
          axisLabelVisible: false,
          title: '',
        });
      } catch (e) {}
    });

    // Delete
    var deleteBtn = popup.querySelector('.dl-delete-btn');
    deleteBtn.addEventListener('click', function () {
      try { panel.candleSeries.removePriceLine(drawLine.priceLine); } catch (e) {}
      for (var i = 0; i < panel._drawLines.length; i++) {
        if (panel._drawLines[i] === drawLine) {
          panel._drawLines.splice(i, 1);
          break;
        }
      }
      _closePopup(panel);
    });

    // Close on outside click
    function outsideClick(e) {
      if (!popup.contains(e.target)) {
        _closePopup(panel);
        document.removeEventListener('mousedown', outsideClick);
      }
    }
    setTimeout(function () { document.addEventListener('mousedown', outsideClick); }, 0);

    container.appendChild(popup);
    panel._drawPopup = popup;
  }

  function _closePopup(panel) {
    if (panel._drawPopup) {
      panel._drawPopup.remove();
      panel._drawPopup = null;
    }
  }

  function setDrawToolActive(active) {
    _globalActive = active;
    document.querySelectorAll('.chart-panel').forEach(function (el) {
      el.style.cursor = active ? 'crosshair' : '';
    });
  }

  function isDrawToolActive() {
    return _globalActive;
  }

  function clearDrawTool(panel) {
    _closePopup(panel);
    if (panel._drawLines) {
      for (var i = 0; i < panel._drawLines.length; i++) {
        try { panel.candleSeries.removePriceLine(panel._drawLines[i].priceLine); } catch (e) {}
      }
      panel._drawLines = [];
    }
  }

  // Persistence: save/restore draw line configs across layout changes
  function getDrawLineConfigs(panel) {
    var configs = [];
    if (panel._drawLines) {
      for (var i = 0; i < panel._drawLines.length; i++) {
        configs.push({ price: panel._drawLines[i].price, color: panel._drawLines[i].color });
      }
    }
    return configs;
  }

  function restoreDrawLines(panel, configs) {
    for (var i = 0; i < configs.length; i++) {
      _createLine(panel, configs[i].price, configs[i].color);
    }
  }

  // Close popup on Escape
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') {
      var panels = document.querySelectorAll('.chart-panel');
      for (var i = 0; i < panels.length; i++) {
        if (panels[i]._drawPopup) _closePopup(panels[i]);
      }
    }
  });

  // Expose globally
  window.initDrawTool = initDrawTool;
  window.setDrawToolActive = setDrawToolActive;
  window.isDrawToolActive = isDrawToolActive;
  window.clearDrawTool = clearDrawTool;
  window.getDrawLineConfigs = getDrawLineConfigs;
  window.restoreDrawLines = restoreDrawLines;
})();
