// ⌘K palette — Alpine component. Index is bootstrapped via
// <script id="palette-index">; matching is fully client-side.

(function () {
  "use strict";

  const RECENTS_KEY = "palette.recents";
  const RECENTS_CAP = 5;
  const RESULTS_CAP = 8;
  const TIER_MULT = { held: 3, targeted: 2, traded: 1 };

  function loadIndex() {
    const empty = { pages: [], tickers: [], actions: [], findings: [] };
    const node = document.getElementById("palette-index");
    if (!node) return empty;
    try {
      const parsed = JSON.parse(node.textContent);
      // Older bootstrap blobs predate actions/findings — fill defaults so
      // we never have to null-check downstream.
      return Object.assign({}, empty, parsed);
    } catch (e) {
      console.error("palette: index parse failed", e);
      return empty;
    }
  }

  function loadRecents() {
    try {
      const raw = localStorage.getItem(RECENTS_KEY);
      return raw ? JSON.parse(raw) : [];
    } catch (e) {
      return [];
    }
  }

  function saveRecents(recents) {
    try {
      localStorage.setItem(RECENTS_KEY, JSON.stringify(recents));
    } catch (e) { /* private mode — ignore */ }
  }

  // Score one item against a query. Returns 0 if no match. Higher = better.
  function score(query, label, aliases) {
    const q = query.toLowerCase();
    const l = label.toLowerCase();
    if (!q) return 0.001; // present but unranked when query empty
    // Exact prefix
    if (l.startsWith(q)) return 100;
    // Word prefix (any word of label or alias)
    const words = l.split(/[\s/-]+/).concat((aliases || []).map((a) => a.toLowerCase()));
    for (const w of words) if (w.startsWith(q)) return 60;
    // Initials (e.g., "th" → "tax harvest")
    const initials = l.split(/[\s/-]+/).map((w) => w[0] || "").join("");
    if (initials.startsWith(q)) return 40;
    // Substring
    if (l.includes(q)) return 20;
    // Aliases substring
    for (const a of aliases || []) if (a.toLowerCase().includes(q)) return 10;
    return 0;
  }

  function rank(query, index) {
    const out = [];
    for (const p of index.pages) {
      const s = score(query, p.label, p.aliases);
      if (s > 0) out.push({ kind: "Page", id: p.route, label: p.label, route: p.route, score: s });
    }
    for (const t of index.tickers) {
      const s = score(query, t.sym, []);
      if (s > 0) {
        const mult = TIER_MULT[t.tier] || 1;
        out.push({
          kind: "Ticker",
          id: t.sym,
          label: t.sym,
          route: `/ticker/${encodeURIComponent(t.sym)}`,
          score: s * mult,
        });
      }
    }
    // Actions ("Sim sell AAPL"). The verb + symbol both rank: typing
    // either "sell" or the symbol surfaces the row, with a small base
    // boost so a strong "sell" prefix doesn't get drowned by 50 tickers.
    for (const a of (index.actions || [])) {
      const s = score(query, a.label, [a.verb, a.sym]);
      if (s > 0) {
        out.push({
          kind: "Action",
          id: a.route,
          label: a.label,
          route: a.route,
          score: s,
        });
      }
    }
    // Findings ("BasisRecon — AAPL/Schwab-Taxable"). All link to /verify;
    // the ranker just helps the user find a specific row by typing the
    // rule_id or the scope (ticker / account label).
    for (const f of (index.findings || [])) {
      const s = score(query, f.label, [f.rule_id, f.scope, f.severity]);
      if (s > 0) {
        out.push({
          kind: "Finding",
          id: `${f.rule_id}|${f.scope}`,
          label: f.label,
          route: f.route,
          score: s,
        });
      }
    }
    out.sort((a, b) => b.score - a.score);
    return out.slice(0, RESULTS_CAP);
  }

  function recentItems(recents, index) {
    // Re-hydrate recents from the current index (drops stale tickers or
    // actions whose target symbol is no longer held).
    const known = new Set([
      ...index.pages.map((p) => `Page:${p.route}`),
      ...index.tickers.map((t) => `Ticker:${t.sym}`),
      ...(index.actions || []).map((a) => `Action:${a.route}`),
    ]);
    const out = [];
    for (const r of recents) {
      const key = `${r.kind}:${r.id}`;
      if (!known.has(key)) continue;
      let label;
      let route;
      if (r.kind === "Ticker") {
        label = r.id;
        route = `/ticker/${encodeURIComponent(r.id)}`;
      } else {
        // Page or Action both store the route as id and the rendered label
        // on the saved entry; tickers are the only kind that re-derives.
        label = r.label;
        route = r.id;
      }
      out.push({ kind: r.kind, id: r.id, label, route, score: 0 });
      if (out.length >= RECENTS_CAP) break;
    }
    return out;
  }

  function paletteOverlay() {
    return {
      open: false,
      query: "",
      results: [],
      activeIndex: 0,
      recents: [],
      _index: { pages: [], tickers: [] },
      _returnFocus: null,

      init() {
        this._index = loadIndex();
        this.recents = loadRecents();
        document.addEventListener("keydown", (e) => this._onGlobalKey(e));
      },

      _isEditableTarget(el) {
        if (!el) return false;
        const tag = el.tagName;
        if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return true;
        return el.isContentEditable === true;
      },

      _onGlobalKey(e) {
        if (this.open) return; // already open; let local handlers run
        const isCmdK = (e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k";
        const isSlash = e.key === "/" && !this._isEditableTarget(e.target);
        if (isCmdK || isSlash) {
          e.preventDefault();
          this.openPalette();
        }
      },

      openPalette() {
        this._returnFocus = document.activeElement;
        this.open = true;
        this.query = "";
        this.activeIndex = 0;
        this.results = recentItems(this.recents, this._index);
        this.$nextTick(() => this.$refs.input && this.$refs.input.focus());
      },

      close() {
        this.open = false;
        if (this._returnFocus && this._returnFocus.focus) this._returnFocus.focus();
      },

      onInput() {
        this.activeIndex = 0;
        if (!this.query) {
          this.results = recentItems(this.recents, this._index);
          return;
        }
        this.results = rank(this.query, this._index);
      },

      move(delta) {
        if (this.results.length === 0) return;
        this.activeIndex = (this.activeIndex + delta + this.results.length) % this.results.length;
        // Keep active row in view.
        this.$nextTick(() => {
          const node = document.getElementById(`palette-row-${this.activeIndex}`);
          if (node) node.scrollIntoView({ block: "nearest" });
        });
      },

      commit(evt, override) {
        const item = override || this.results[this.activeIndex];
        if (!item) return;
        // Record recent. Findings are ephemeral (they change on every
        // verify run) so we don't persist them. Tickers persist by sym;
        // pages and actions persist by route+label.
        if (item.kind !== "Finding") {
          const recent = item.kind === "Ticker"
            ? { kind: "Ticker", id: item.id }
            : { kind: item.kind, id: item.id, label: item.label };
          this.recents = [recent, ...this.recents.filter((r) => !(r.kind === recent.kind && r.id === recent.id))].slice(0, RECENTS_CAP);
          saveRecents(this.recents);
        }
        const newTab = evt && (evt.metaKey || evt.ctrlKey);
        // Same-page navigation in the same tab would reload the page, wiping
        // any in-progress form state. Close the palette and stay put instead.
        // Cmd/Ctrl-click (new tab) always proceeds — it's a deliberate
        // "open same page in new tab" gesture.
        try {
          const targetUrl = new URL(item.route, window.location.origin);
          const sameUrl =
            targetUrl.pathname === window.location.pathname &&
            targetUrl.search === window.location.search &&
            targetUrl.hash === window.location.hash;
          if (sameUrl && !newTab) {
            this.close();
            return;
          }
        } catch (e) { /* malformed route — fall through to navigate */ }
        if (newTab) window.open(item.route, "_blank");
        else window.location.href = item.route;
        this.close();
      },
    };
  }

  // Expose the factory globally so `x-data="paletteOverlay()"` in
  // _palette.html resolves regardless of how Alpine's eval scope is set
  // up. Alpine.data() registration is timing-fragile across defer-load
  // orderings; a window-scoped factory is unambiguous and survives every
  // hot-reload + cache-buster path we've tested.
  window.paletteOverlay = paletteOverlay;
})();
