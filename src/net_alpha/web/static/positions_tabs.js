// Per-tab page-cursor memory for the Positions page.
// On tab click: append cached &page= to the destination if we have one.
// On page load: write the current ?page= value into the cache for the
// active view.
(function () {
  const STORAGE_PREFIX = "positions.page.";

  function getCachedPage(view) {
    try {
      const v = localStorage.getItem(STORAGE_PREFIX + view);
      return v && /^\d+$/.test(v) ? parseInt(v, 10) : null;
    } catch (_) {
      return null;
    }
  }

  function setCachedPage(view, page) {
    try {
      if (page && page > 1) {
        localStorage.setItem(STORAGE_PREFIX + view, String(page));
      } else {
        localStorage.removeItem(STORAGE_PREFIX + view);
      }
    } catch (_) {}
  }

  function rewriteWithCachedPage(href, view) {
    const cached = getCachedPage(view);
    if (!cached) return href;
    const url = new URL(href, window.location.origin);
    if (url.searchParams.has("page")) return href;
    url.searchParams.set("page", String(cached));
    return url.pathname + "?" + url.searchParams.toString();
  }

  function init() {
    const root = document.querySelector("[data-positions-tabs-root]");
    if (!root) return;

    const params = new URLSearchParams(window.location.search);
    const currentView = params.get("view") || "all";
    const currentPage = parseInt(params.get("page") || "1", 10);
    setCachedPage(currentView, currentPage);

    root.querySelectorAll("a[data-view-tab]").forEach((a) => {
      a.addEventListener("click", (e) => {
        const view = a.dataset.viewTab;
        if (!view || view === currentView) return;
        const rewritten = rewriteWithCachedPage(a.getAttribute("href"), view);
        if (rewritten !== a.getAttribute("href")) {
          e.preventDefault();
          window.location.href = rewritten;
        }
      });
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
