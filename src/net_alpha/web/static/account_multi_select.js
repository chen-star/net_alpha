// Alpine helper for the multi-account checkbox dropdown rendered by the
// _account_multi_select.html macro. Loaded in base.html with defer so it
// runs before alpine.min.js initializes — otherwise Alpine evaluates the
// macro's x-data="accountMultiSelect()" before the inline <script> at the
// tail of the macro has had a chance to register the function, and the
// scope evaluates to `undefined` (cascading into picked / selectedNames /
// currentLabel reference errors).

function accountMultiSelect() {
  return {
    open: false,
    _timer: null,
    currentLabel: 'All accounts',
    picked: 0,
    selectedNames: [],
    init() {
      this.recompute();
    },
    recompute() {
      const root = this.$root;
      const total = parseInt(root.getAttribute('data-total-accounts'), 10) || 0;
      const checked = Array.from(root.querySelectorAll('input[type=checkbox][name]'))
        .filter(cb => cb.checked);
      this.selectedNames = checked.map(cb => cb.value);
      this.picked = checked.length;
      if (this.picked === 0) {
        this.currentLabel = 'All accounts';
      } else if (this.picked === 1) {
        this.currentLabel = this.selectedNames[0];
      } else {
        this.currentLabel = this.picked + ' of ' + total + ' accounts';
      }
    },
    onToggle() {
      this.recompute();
      clearTimeout(this._timer);
      this._timer = setTimeout(() => {
        const form = this.$root.closest('form');
        if (!form) return;
        if (form.hasAttribute('hx-get') || form.hasAttribute('hx-post')) {
          form.dispatchEvent(new Event('change', { bubbles: true }));
        } else {
          form.requestSubmit();
        }
      }, 200);
    },
    toggleAll(checked) {
      const root = this.$root;
      root.querySelectorAll('input[type=checkbox][name]').forEach(cb => { cb.checked = checked; });
      this.onToggle();
    },
  };
}
