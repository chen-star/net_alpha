/**
 * net-alpha shared ApexCharts theme + helpers.
 * Loaded by base.html (as a non-module script). Sets a global namespace.
 */
(function () {
  const colors = {
    pos:      "#30D158",
    neg:      "#FF453A",
    indigo:   "#5E5CE6",
    violet:   "#BF5AF2",
    info:     "#64D2FF",
    label2:   "rgba(235,235,245,0.6)",
    label3:   "rgba(235,235,245,0.35)",
    hairline: "rgba(255,255,255,0.08)",
    surface:  "#1C1C1E",
    bg:       "#000000",
  };

  // Default options shared across all dark charts.
  const defaults = {
    chart: {
      background: "transparent",
      foreColor: colors.label2,
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
    theme: { mode: "dark" },
    grid: {
      borderColor: colors.hairline,
      strokeDashArray: 2,
      xaxis: { lines: { show: false } },
      yaxis: { lines: { show: true } },
      padding: { top: 8, right: 8, bottom: 4, left: 8 },
    },
    xaxis: {
      labels: {
        style: { colors: colors.label3, fontSize: "10px", fontFamily: "JetBrains Mono, ui-monospace, monospace" },
      },
      axisBorder: { color: colors.hairline },
      axisTicks: { color: colors.hairline },
    },
    yaxis: {
      labels: {
        style: { colors: colors.label3, fontSize: "10px", fontFamily: "JetBrains Mono, ui-monospace, monospace" },
      },
    },
    tooltip: {
      theme: "dark",
      style: { fontSize: "12px", fontFamily: "Inter, sans-serif" },
    },
    dataLabels: { enabled: false },
    legend: {
      labels: { colors: colors.label2 },
      fontSize: "12px",
      fontFamily: "Inter, sans-serif",
    },
    stroke: { curve: "smooth", width: 2, lineCap: "round" },
  };

  function merge(a, b) {
    const out = Object.assign({}, a);
    for (const k in b) {
      if (b[k] && typeof b[k] === "object" && !Array.isArray(b[k])) {
        out[k] = merge(a[k] || {}, b[k]);
      } else {
        out[k] = b[k];
      }
    }
    return out;
  }

  window.netAlphaChartTheme = { colors, defaults, merge };
})();
