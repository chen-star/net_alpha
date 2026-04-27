// Named Alpine component for the multi-symbol filter on the Holdings toolbar.
// Extracted from inline x-data so the multi-line JS doesn't leak as visible text
// when Alpine fails to evaluate the expression.

function registerSymbolFilter() {
  window.Alpine.data('symbolFilter', (config) => ({
    open: false,
    query: '',
    selected: config.selected || [],
    all: config.all || [],
    qsTemplate: config.qsTemplate || '',
    show: config.show || 'open',
    pageSize: config.pageSize || 25,

    toggle(s) {
      const i = this.selected.indexOf(s);
      if (i === -1) this.selected.push(s);
      else this.selected.splice(i, 1);
    },

    filtered() {
      const q = this.query.trim().toUpperCase();
      return q ? this.all.filter((s) => s.toUpperCase().includes(q)) : this.all;
    },

    label() {
      if (this.selected.length === 0) return 'Symbols: All';
      if (this.selected.length <= 2) return 'Symbols: ' + this.selected.join(', ');
      return (
        'Symbols: ' +
        this.selected.slice(0, 2).join(', ') +
        ' +' +
        (this.selected.length - 2)
      );
    },

    apply() {
      this.open = false;
      const url =
        '/portfolio/positions?' +
        this.qsTemplate.replace(
          /symbols=[^&]*/,
          'symbols=' + encodeURIComponent(this.selected.join(','))
        ) +
        '&show=' +
        this.show +
        '&page=1&page_size=' +
        this.pageSize;
      htmx.ajax('GET', url, { target: '#holdings-positions', swap: 'innerHTML' });
    },

    clear() {
      this.selected = [];
      this.apply();
    },
  }));
}

// Alpine 3 starts via queueMicrotask before deferred scripts run, so listening
// for `alpine:init` from a <script defer> can miss the event. Register now if
// Alpine is already loaded, otherwise queue for `alpine:init`.
if (window.Alpine) {
  registerSymbolFilter();
} else {
  document.addEventListener('alpine:init', registerSymbolFilter);
}
