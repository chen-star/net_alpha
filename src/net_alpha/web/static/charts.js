/**
 * net-alpha shared ApexCharts theme + helpers.
 *
 * Loaded by base.html (as a non-module script). Sets a global namespace.
 *
 * Colors and the Apex `tooltip.theme` mode are read live from the active
 * CSS custom properties (so [data-theme="light"] / [data-theme="dark"]
 * just works), and a registry of inline render() functions re-renders
 * every chart on the `theme:change` window event dispatched by theme.js.
 */
(function () {
  function readVar(name) {
    var v = getComputedStyle(document.documentElement).getPropertyValue(name);
    return v ? v.trim() : "";
  }

  function readColors() {
    return {
      pos:      readVar("--color-pos")      || "#30D158",
      neg:      readVar("--color-neg")      || "#FF453A",
      indigo:   readVar("--color-indigo")   || "#5E5CE6",
      violet:   readVar("--color-violet")   || "#BF5AF2",
      info:     readVar("--color-info")     || "#64D2FF",
      warn:     readVar("--color-warn")     || "#FF9F0A",
      label1:   readVar("--color-label-1")  || "rgba(235,235,245,0.92)",
      label2:   readVar("--color-label-2")  || "rgba(235,235,245,0.6)",
      label3:   readVar("--color-label-3")  || "rgba(235,235,245,0.35)",
      hairline: readVar("--color-hairline") || "rgba(255,255,255,0.08)",
      surface:  readVar("--color-surface")  || "#1C1C1E",
      bg:       readVar("--color-bg")       || "#000000",
    };
  }

  function activeTheme() {
    return document.documentElement.getAttribute("data-theme") === "light" ? "light" : "dark";
  }

  // Live `colors` view — reading any property re-resolves against the
  // current CSS variables, so existing call sites that say
  // `window.netAlphaChartTheme.colors.pos` always get the active-theme value.
  var colors = new Proxy({}, {
    get: function (_target, key) {
      var snapshot = readColors();
      return snapshot[key];
    },
  });

  function buildDefaults() {
    var c = readColors();
    var isLight = activeTheme() === "light";
    // In dark mode label3 (35% white) reads fine on near-black; in light
    // mode the same opacity on white falls below WCAG, so step axis labels
    // up to label2 (60%) and legend up to label1 (~85%).
    var axisColor = isLight ? c.label2 : c.label3;
    var legendColor = isLight ? c.label1 : c.label2;
    return {
      chart: {
        background: "transparent",
        foreColor: legendColor,
        fontFamily: "Inter, -apple-system, system-ui, sans-serif",
        toolbar: { show: false },
        zoom: { enabled: false },
        animations: {
          enabled: true,
          easing: "easeinout",
          speed: 800,
          animateGradually: { enabled: false },
          dynamicAnimation: { enabled: false },
        },
      },
      theme: { mode: activeTheme() },
      grid: {
        borderColor: c.hairline,
        strokeDashArray: 2,
        xaxis: { lines: { show: false } },
        yaxis: { lines: { show: true } },
        padding: { top: 8, right: 8, bottom: 4, left: 8 },
      },
      xaxis: {
        labels: {
          style: { colors: axisColor, fontSize: "10px", fontFamily: "JetBrains Mono, ui-monospace, monospace" },
        },
        axisBorder: { color: c.hairline },
        axisTicks: { color: c.hairline },
      },
      yaxis: {
        labels: {
          style: { colors: axisColor, fontSize: "10px", fontFamily: "JetBrains Mono, ui-monospace, monospace" },
        },
      },
      tooltip: {
        theme: activeTheme(),
        style: { fontSize: "12px", fontFamily: "Inter, sans-serif" },
      },
      dataLabels: { enabled: false },
      legend: {
        labels: { colors: legendColor },
        fontSize: "12px",
        fontFamily: "Inter, sans-serif",
      },
      stroke: { curve: "smooth", width: 2, lineCap: "round" },
    };
  }

  // `defaults` is a getter so per-chart templates that read it during render
  // always pick up live theme values instead of a snapshot from page load.
  var defaultsHandle = {
    get value() { return buildDefaults(); },
  };

  function merge(a, b) {
    var out = Object.assign({}, a);
    for (var k in b) {
      if (b[k] && typeof b[k] === "object" && !Array.isArray(b[k])) {
        out[k] = merge(a[k] || {}, b[k]);
      } else {
        out[k] = b[k];
      }
    }
    return out;
  }

  // Registry of render functions. Each chart template wraps its inline
  // render() with `register(render)` so theme switches can re-invoke them.
  var registry = [];

  function register(fn) {
    if (typeof fn === "function") {
      registry.push(fn);
      // Run it now so the chart appears on initial load.
      fn();
    }
  }

  function refresh() {
    for (var i = 0; i < registry.length; i++) {
      try { registry[i](); } catch (e) { /* a single chart failure shouldn't kill others */ }
    }
  }

  window.addEventListener("theme:change", refresh);

  // Expose. `defaults` keeps property semantics for back-compat with
  // existing per-chart code that calls `merge(defaults, {...})`.
  window.netAlphaChartTheme = {
    colors: colors,
    get defaults() { return defaultsHandle.value; },
    merge: merge,
    register: register,
    refresh: refresh,
  };
})();
