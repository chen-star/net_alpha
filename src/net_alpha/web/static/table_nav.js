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

// Pane keyboard nav (j/k row stepping, o opens ticker). Active only when:
//   1) the side pane is open (Alpine `open` state on #positions-pane), AND
//   2) the user is not focused on an input/textarea/select/contenteditable
//      element (so j/k don't hijack typing).
// On each step, dispatch the existing `open-positions-pane` custom event
// with the new row's sym + account_id — the aside's Alpine handler picks
// it up and re-fetches the pane body via HTMX.
(function () {
  function paneIsOpen() {
    const aside = document.getElementById("positions-pane");
    if (!aside) return false;
    return getComputedStyle(aside).display !== "none";
  }

  function focusedInInput() {
    const ae = document.activeElement;
    if (!ae) return false;
    return /^(input|textarea|select)$/i.test(ae.tagName) || ae.isContentEditable;
  }

  function visibleRows() {
    const container = document.querySelector("#holdings-positions");
    if (!container) return [];
    const rows = Array.from(container.querySelectorAll('tr[data-row="position"]'));
    return rows.filter((r) => r.offsetParent !== null);
  }

  function currentSym() {
    const aside = document.getElementById("positions-pane");
    if (!aside) return null;
    try {
      const data = window.Alpine && window.Alpine.$data(aside);
      return data ? data.sym : null;
    } catch (e) {
      console.warn("[positions-pane] Alpine.$data() failed — check Alpine version", e);
      return null;
    }
  }

  function step(delta) {
    const rows = visibleRows();
    if (rows.length === 0) return;
    const sym = currentSym();
    let idx = rows.findIndex((r) => r.dataset.symbol === sym);
    if (idx === -1) idx = 0;
    const next = rows[(idx + delta + rows.length) % rows.length];
    const detail = {
      sym: next.dataset.symbol,
      account_id: next.dataset.accountId || null,
    };
    window.dispatchEvent(new CustomEvent("open-positions-pane", { detail }));
  }

  document.addEventListener("keydown", function (e) {
    if (!paneIsOpen()) return;
    if (focusedInInput()) return;
    if (e.metaKey || e.ctrlKey || e.altKey) return;
    if (e.key === "j") {
      e.preventDefault();
      step(+1);
    } else if (e.key === "k") {
      e.preventDefault();
      step(-1);
    } else if (e.key === "o") {
      const sym = currentSym();
      if (sym) window.open("/ticker/" + encodeURIComponent(sym), "_blank");
    }
  });
})();
