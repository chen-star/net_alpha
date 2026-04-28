// Per-page density override stored in localStorage. The persistent
// default is in user_preferences.density (server-side); this lets the
// next page render reflect a click *before* the round-trip completes,
// and survives across reloads on the same page+account.
//
// Key shape: density:{page_key}:{account_id_or_all}
//   e.g., "density:/holdings:42"  or  "density:/tax:all"

(function () {
  function keyFor(page, account) {
    return "density:" + page + ":" + (account || "all");
  }

  window.recordDensityOverride = function (pageKey, density) {
    try {
      var account = (new URLSearchParams(window.location.search)).get("account") || "all";
      window.localStorage.setItem(keyFor(pageKey, account), density);
    } catch (_) { /* localStorage disabled — fall back to DB default */ }
  };

  window.applyDensityFromLocalStorage = function (rootEl) {
    try {
      var page = rootEl.getAttribute("data-page-key");
      if (!page) return;
      var account = (new URLSearchParams(window.location.search)).get("account") || "all";
      var stored = window.localStorage.getItem(keyFor(page, account));
      if (!stored) return;
      // Tag the body so CSS rules can adjust per-density without reload.
      document.body.setAttribute("data-density-override", stored);
    } catch (_) { /* noop */ }
  };
})();
