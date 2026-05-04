// Plan-tab drag-to-reorder. Attaches SortableJS to #plan-tbody when the
// Plan tab is rendered in Manual sort mode. POSTs the new order to
// /positions/plan/reorder via fetch and swaps the re-rendered body in.
//
// Safe on every page: this is a no-op if #plan-tbody is missing or its
// data-sort-mode != 'manual'.

(function () {
  function initPlanSortable() {
    var tbody = document.getElementById('plan-tbody');
    if (!tbody || tbody.dataset.sortMode !== 'manual') return;
    if (tbody._sortableAttached) return;
    if (typeof Sortable === 'undefined') return;
    tbody._sortableAttached = true;

    Sortable.create(tbody, {
      handle: '.drag-handle',
      animation: 150,
      ghostClass: 'plan-row-ghost',
      onEnd: function () {
        var symbols = [];
        tbody.querySelectorAll('tr[data-symbol]').forEach(function (tr) {
          symbols.push(tr.dataset.symbol);
        });

        var params = new URLSearchParams();
        symbols.forEach(function (s) { params.append('order', s); });

        // Propagate current view context so the re-render preserves filter
        // and page state.
        var here = new URLSearchParams(window.location.search);
        ['account', 'tag', 'page'].forEach(function (k) {
          var v = here.get(k);
          if (v) params.append(k, v);
        });

        // fetch+innerHTML rather than htmx.ajax: htmx.ajax's `values` option
        // does not support repeated keys, and we need form-encoded multiple
        // `order` entries.
        fetch('/positions/plan/reorder', {
          method: 'POST',
          headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
          body: params.toString(),
        })
          .then(function (r) { return r.text(); })
          .then(function (html) {
            var planBody = document.getElementById('plan-body');
            if (!planBody) return;
            var tmp = document.createElement('div');
            tmp.innerHTML = html;
            var fresh = tmp.querySelector('#plan-body') || tmp.firstElementChild;
            if (fresh) {
              planBody.replaceWith(fresh);
              if (window.htmx && typeof htmx.process === 'function') {
                htmx.process(fresh);
              }
              document.body.dispatchEvent(new CustomEvent('htmx:afterSwap', {
                detail: { target: fresh },
              }));
            }
          });
      },
    });
  }

  document.addEventListener('DOMContentLoaded', initPlanSortable);
  document.body.addEventListener('htmx:afterSwap', initPlanSortable);
  // Expose for hand-testing in DevTools.
  window.__initPlanSortable = initPlanSortable;
})();
