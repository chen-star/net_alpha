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

  document.addEventListener("keydown", (e) => {
    if (isTypingTarget(e.target)) { awaiting = null; return; }
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
