// Global keyboard shortcuts. Disabled while typing inside <input>/<textarea>/<select>.
(function () {
  const SHORTCUTS = {
    "g o": "/",
    "g p": "/positions",
    "g t": "/tax",
    "g s": "/sim",
  };

  let awaiting = null; // "g" while waiting for the second key, else null
  let resetTimer = null;

  function isTypingTarget(el) {
    if (!el) return false;
    const tag = el.tagName;
    return (
      tag === "INPUT" ||
      tag === "TEXTAREA" ||
      tag === "SELECT" ||
      el.isContentEditable
    );
  }

  // True when any overlay (modal, palette, cheatsheet, drawer) is on screen.
  // Without this, pressing `,` or `g o` while a delete-confirm modal is up
  // would navigate away from the partially-completed action.
  function isOverlayOpen() {
    if (document.querySelector("dialog[open]")) return true;
    const dialogs = document.querySelectorAll("[role=dialog]");
    for (const d of dialogs) {
      if (d.hasAttribute("hidden")) continue;
      if (d.classList.contains("hidden")) continue;
      // Alpine x-show / x-cloak set style.display='none' while closed.
      if (d.style && d.style.display === "none") continue;
      return true;
    }
    for (const id of ["trade-modal", "import-modal", "settings-drawer"]) {
      const el = document.getElementById(id);
      if (el && !el.classList.contains("hidden") && !(el.style && el.style.display === "none")) return true;
    }
    return false;
  }

  document.addEventListener("keydown", (e) => {
    if (isTypingTarget(e.target)) { awaiting = null; return; }
    if (isOverlayOpen()) { awaiting = null; return; }
    if (e.metaKey || e.ctrlKey || e.altKey) return;

    if (e.key === "?") {
      e.preventDefault();
      window.dispatchEvent(new CustomEvent("open-keyboard-cheatsheet"));
      awaiting = null;
      return;
    }
    if (e.key === ",") {
      e.preventDefault();
      window.dispatchEvent(new CustomEvent("open-settings-drawer", { detail: { tab: "imports" } }));
      awaiting = null;
      return;
    }

    if (awaiting === "g") {
      const target = SHORTCUTS["g " + e.key];
      awaiting = null;
      clearTimeout(resetTimer);
      if (target) {
        e.preventDefault();
        window.location.href = target;
      }
      return;
    }

    if (e.key === "g") {
      awaiting = "g";
      clearTimeout(resetTimer);
      resetTimer = setTimeout(() => { awaiting = null; }, 800);
    }
  });
})();
