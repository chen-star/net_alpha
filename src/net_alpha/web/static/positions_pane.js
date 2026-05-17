// Sticky-open: when the underlying positions table re-renders (HTMX swap
// after a filter change or after the symbol search applies), check
// whether the currently-open symbol still has a visible row. If yes — keep
// the pane open. If not — close it.
//
// Hooks into two seams:
//   - htmx:afterSwap on (or scoped to) #holdings-positions
//   - window.__applyPositionsSymbolFilter (wrapped to re-check after apply)
//
// The pane's open/close state is Alpine-managed on the #positions-pane
// aside; we toggle it via window.Alpine.$data(aside).open (v3 API).
(function () {
  function paneAside() { return document.getElementById('positions-pane'); }

  function visibleSymbols() {
    var container = document.querySelector('#holdings-positions');
    if (!container) return new Set();
    var rows = Array.from(container.querySelectorAll('tr[data-row="position"]'));
    return new Set(
      rows.filter(function (r) { return r.offsetParent !== null; }).map(function (r) { return r.dataset.symbol; })
    );
  }

  function currentSym() {
    var aside = paneAside();
    if (!aside) return null;
    try {
      var data = window.Alpine && window.Alpine.$data(aside);
      return data ? data.sym : null;
    } catch (e) {
      console.warn('[positions-pane] Alpine.$data() failed — check Alpine version', e);
      return null;
    }
  }

  function maybeCloseIfHidden() {
    var aside = paneAside();
    if (!aside) return;
    var sym = currentSym();
    if (!sym) return;
    var visible = visibleSymbols();
    if (!visible.has(sym)) {
      try {
        var data = window.Alpine && window.Alpine.$data(aside);
        if (data) data.open = false;
      } catch (e) {
        console.warn('[positions-pane] Alpine.$data() failed — could not close pane', e);
      }
    }
  }

  // After any HTMX swap that re-renders the holdings table, re-check.
  document.addEventListener('htmx:afterSwap', function (evt) {
    var target = evt.detail && evt.detail.target;
    if (!target) return;
    if (target.id === 'holdings-positions') {
      maybeCloseIfHidden();
      return;
    }
    if (target.closest && target.closest('#holdings-positions')) {
      maybeCloseIfHidden();
    }
  });

  // The symbol-search filter is client-side (positions_search.js exposes
  // `window.__applyPositionsSymbolFilter`). Wrap it so we re-check after
  // each apply. Use a poll-and-wrap pattern in case load order shifts.
  function wrapApplyFilter() {
    var orig = window.__applyPositionsSymbolFilter;
    if (typeof orig !== 'function' || orig.__panePatched) return;
    window.__applyPositionsSymbolFilter = function () {
      var r = orig.apply(this, arguments);
      maybeCloseIfHidden();
      return r;
    };
    window.__applyPositionsSymbolFilter.__panePatched = true;
  }

  if (document.readyState !== 'loading') {
    wrapApplyFilter();
  } else {
    document.addEventListener('DOMContentLoaded', wrapApplyFilter);
  }
})();
