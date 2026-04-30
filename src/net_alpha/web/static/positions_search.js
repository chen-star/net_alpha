// Client-side symbol filter for the Positions page.
//
// One search box on /positions filters every visible row across all tabs by
// underlying ticker. Rows opt in via `data-symbol="TICKER"` (uppercased).
// Options carry the underlying ticker, so typing "SPY" matches every SPY
// option contract automatically.
//
// HTMX swaps in tab fragments after page load, so we re-apply the filter on
// `htmx:afterSwap`.

(function () {
  function applyFilter(query) {
    const q = (query || "").toUpperCase().trim();
    const rows = document.querySelectorAll("[data-symbol]");
    rows.forEach((el) => {
      const sym = (el.getAttribute("data-symbol") || "").toUpperCase();
      if (!q || sym.includes(q)) {
        el.style.display = "";
      } else {
        el.style.display = "none";
      }
    });
  }

  function currentQuery() {
    const input = document.querySelector("[data-symbol-search]");
    return input ? input.value : "";
  }

  window.__applyPositionsSymbolFilter = applyFilter;

  document.body.addEventListener("htmx:afterSwap", function () {
    applyFilter(currentQuery());
  });
})();
