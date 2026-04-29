// Global keyboard shortcuts. Disabled while typing inside <input>/<textarea>/<select>.
(function () {
  const SHORTCUTS = {
    "g o": "/",
    "g p": "/positions",
    "g t": "/tax",
    "g s": "/sim",
  };

  let pending = "";
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
    if (isTypingTarget(e.target)) return;
    if (e.metaKey || e.ctrlKey || e.altKey) return;

    if (e.key === "?") {
      e.preventDefault();
      window.dispatchEvent(new CustomEvent("open-keyboard-cheatsheet"));
      return;
    }
    if (e.key === ",") {
      e.preventDefault();
      window.dispatchEvent(new CustomEvent("open-settings-drawer", { detail: { tab: "imports" } }));
      return;
    }

    if (e.key.length === 1) {
      pending = (pending + e.key).slice(-3);
      const candidate = pending.replace(/(.)(?=.)/g, "$1 ");
      // Try last 3 chars as "x y", and last 1 char as single
      for (const seq of Object.keys(SHORTCUTS)) {
        if (pending.endsWith(seq.replace(" ", ""))) {
          window.location.href = SHORTCUTS[seq];
          pending = "";
          return;
        }
      }
      clearTimeout(resetTimer);
      resetTimer = setTimeout(() => { pending = ""; }, 800);
    }
  });
})();
