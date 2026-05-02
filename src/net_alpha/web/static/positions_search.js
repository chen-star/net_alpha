// Client-side symbol filter for the Positions page.
//
// One search box on /positions filters every visible row across all tabs by
// underlying ticker. Rows opt in via `data-symbol="TICKER"` (uppercased).
// Options carry the underlying ticker, so typing "SPY" matches every SPY
// option contract automatically.
//
// HTMX swaps in tab fragments after page load, so we re-apply the filter on
// `htmx:afterSwap`.
//
// The All/Stocks tabs paginate `/portfolio/positions` server-side at
// PAGE_SIZE=25, so a pure DOM filter can't see rows on later pages. When a
// query is non-empty we also fire a debounced HTMX request to refresh
// `#holdings-positions` with `q=<query>` so the server returns any matching
// row regardless of page.

(function () {
  const HOLDINGS_ID = "holdings-positions";

  function applyClientFilter(query) {
    const q = (query || "").toUpperCase().trim();
    document.querySelectorAll("[data-symbol]").forEach((el) => {
      const sym = (el.getAttribute("data-symbol") || "").toUpperCase();
      el.style.display = !q || sym.includes(q) ? "" : "none";
    });
  }

  let _holdingsTimer = null;
  let _holdingsLastQ = null;

  function refreshPaginatedHoldings(query) {
    const target = document.getElementById(HOLDINGS_ID);
    if (!target) return;
    const baseURL = target.getAttribute("hx-get") || "";
    if (!baseURL) return;
    const q = (query || "").trim();
    if (_holdingsTimer) clearTimeout(_holdingsTimer);
    _holdingsTimer = setTimeout(() => {
      if (q === _holdingsLastQ) return;
      _holdingsLastQ = q;
      const sep = baseURL.includes("?") ? "&" : "?";
      const url = q ? `${baseURL}${sep}q=${encodeURIComponent(q)}` : baseURL;
      if (window.htmx) {
        window.htmx.ajax("GET", url, { target: "#" + HOLDINGS_ID, swap: "innerHTML" });
      }
    }, 200);
  }

  function applyFilter(query) {
    applyClientFilter(query);
    refreshPaginatedHoldings(query);
  }

  function currentQuery() {
    const input = document.querySelector("[data-symbol-search]");
    return input ? input.value : "";
  }

  window.__applyPositionsSymbolFilter = applyFilter;

  document.body.addEventListener("htmx:afterSwap", function () {
    applyClientFilter(currentQuery());
  });
})();
