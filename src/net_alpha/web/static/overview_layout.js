// Overview drag-to-reorder. Attaches SortableJS to #overview-rows only
// when data-edit-mode="on". POSTs the new row order to
// /portfolio/layout/reorder. No-op outside edit mode and outside the
// Overview page.

(function () {
  function rowsRoot() {
    return document.getElementById('overview-rows');
  }

  function initOverviewSortable() {
    const root = rowsRoot();
    if (!root) return;
    if (root.dataset.editMode !== 'on') {
      if (root._sortableInstance) {
        root._sortableInstance.destroy();
        root._sortableInstance = null;
      }
      return;
    }
    if (root._sortableInstance) return;
    if (typeof Sortable === 'undefined') return;

    root._sortableInstance = Sortable.create(root, {
      handle: '[data-handle]',
      animation: 150,
      ghostClass: 'overview-row-ghost',
      disabled: window.matchMedia('(max-width: 767px)').matches,
      onEnd: function () {
        const rows = Array.from(root.querySelectorAll('[data-row-key]'))
          .map(function (el) { return el.dataset.rowKey; });
        const params = new URLSearchParams();
        rows.forEach(function (r) { params.append('row', r); });
        fetch('/portfolio/layout/reorder', {
          method: 'POST',
          headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
          body: params.toString(),
        })
          .then(function (r) {
            if (!r.ok) console.warn('overview reorder failed:', r.status);
          })
          .catch(function (err) {
            console.warn('overview reorder error:', err);
          });
      },
    });
  }

  document.addEventListener('DOMContentLoaded', initOverviewSortable);
  document.body.addEventListener('htmx:afterSwap', initOverviewSortable);
  document.body.addEventListener('overview:edit-mode-change', initOverviewSortable);

  window.__initOverviewSortable = initOverviewSortable;
})();
