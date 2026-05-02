/**
 * net-alpha theme switcher.
 *
 * Called by the appearance toggle's onclick handler before the HX-POST
 * round-trip so the UI flips immediately. Writes the choice to localStorage
 * (so the FOUC script picks it up on next nav even before the server pref
 * has been fetched), resolves 'system' against the OS preference, sets
 * data-theme on <html>, and dispatches a `theme:change` event so charts
 * (and any other listeners) can re-render.
 */
(function () {
  function resolve(pref) {
    if (pref === "system") {
      return window.matchMedia && window.matchMedia("(prefers-color-scheme: light)").matches
        ? "light"
        : "dark";
    }
    return pref;
  }

  window.applyThemeChoice = function (pref) {
    try { localStorage.setItem("theme", pref); } catch (e) {}
    var resolved = resolve(pref);
    document.documentElement.setAttribute("data-theme", resolved);
    document.documentElement.dataset.themePref = pref;
    window.dispatchEvent(new CustomEvent("theme:change", { detail: { theme: resolved } }));
  };
})();
