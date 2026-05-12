// Arrow-key row navigation for long tables that opt in via `data-table-nav`
// on their <tbody>. ↑/↓ move focus between <tr>s; Enter follows the row's
// primary action (first <a> in the row).
(function () {
  function isTypingTarget(el) {
    if (!el) return false;
    return ["INPUT", "TEXTAREA", "SELECT"].includes(el.tagName) || el.isContentEditable;
  }

  function rows(tbody) {
    return Array.from(tbody.querySelectorAll("tr[tabindex='0']"));
  }

  function attach(tbody) {
    tbody.querySelectorAll("tr").forEach((tr) => {
      if (!tr.hasAttribute("tabindex")) tr.setAttribute("tabindex", "0");
    });

    tbody.addEventListener("keydown", (e) => {
      if (isTypingTarget(e.target)) return;
      if (e.metaKey || e.ctrlKey || e.altKey) return;

      const tr = e.target.closest("tr");
      if (!tr || tr.parentElement !== tbody) return;
      const all = rows(tbody);
      const idx = all.indexOf(tr);
      if (idx < 0) return;

      if (e.key === "ArrowDown") {
        e.preventDefault();
        const next = all[Math.min(idx + 1, all.length - 1)];
        if (next) next.focus();
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        const prev = all[Math.max(idx - 1, 0)];
        if (prev) prev.focus();
      } else if (e.key === "Enter") {
        const primary = tr.querySelector("a, button");
        if (primary) {
          e.preventDefault();
          primary.click();
        }
      }
    });
  }

  function init() {
    document.querySelectorAll("tbody[data-table-nav]").forEach(attach);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
  // Re-init after HTMX swaps (e.g. harvest pagination, future row insertions).
  document.body.addEventListener("htmx:afterSwap", init);
})();
