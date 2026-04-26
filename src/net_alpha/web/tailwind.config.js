/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/net_alpha/web/templates/**/*.html"],
  safelist: [
    // semantic colors used dynamically in templates
    { pattern: /^bg-(surface|surface-2|surface-3|pos|neg|warn|info|indigo|violet)$/ },
    { pattern: /^text-(label-1|label-2|label-3|pos|neg|warn|info|indigo|violet)$/ },
    { pattern: /^border-(hairline|hairline-strong|pos|neg|warn|info|indigo|violet)$/ },
    // chip variants
    "chip", "chip-confirm", "chip-probable", "chip-unclear",
    // KPI hero halo
    "kpi-hero",
    // segmented buttons
    "seg", "seg-active",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['-apple-system', '"SF Pro Display"', '"Inter"', 'system-ui', 'sans-serif'],
        mono: ['"SF Mono"', '"JetBrains Mono"', 'ui-monospace', 'Menlo', 'monospace'],
      },
      colors: {
        // Canvas
        bg:          "#000000",
        surface:     "#1C1C1E",
        "surface-2": "#2C2C2E",
        "surface-3": "#3A3A3C",
        // Hairline (transparent — exposed as utility too)
        hairline:        "rgba(255,255,255,0.08)",
        "hairline-strong": "rgba(255,255,255,0.14)",
        // Text
        text:      "#FFFFFF",
        "label-1": "rgba(235,235,245,0.92)",
        "label-2": "rgba(235,235,245,0.60)",
        "label-3": "rgba(235,235,245,0.35)",
        // Brand cyber
        indigo:  "#5E5CE6",
        violet:  "#BF5AF2",
        // Semantic — P/L
        pos:    "#30D158",
        neg:    "#FF453A",
        // Semantic — status
        warn:   "#FF9F0A",
        info:   "#64D2FF",
        // Allocation rank palette (slot-bound)
        "rank-1":  "#0A84FF",
        "rank-2":  "#FFD60A",
        "rank-3":  "#30D158",
        "rank-4":  "#FF375F",
        "rank-5":  "#5E5CE6",
        "rank-6":  "#64D2FF",
        "rank-7":  "#5AC8FA",
        "rank-8":  "#BF5AF2",
        "rank-9":  "rgba(181,181,255,0.65)",
        "rank-10": "rgba(255,255,255,0.40)",
        "rank-rest": "rgba(255,255,255,0.14)",
        // Back-compat aliases for existing class refs (badge-confirmed etc.)
        confirmed: "#FF453A",
        probable:  "#FF9F0A",
        unclear:   "#64D2FF",
        primary:   "#0A84FF",
        secondary: "#5E5CE6",
        accent:    "#BF5AF2",
        ink:       "#FFFFFF",
      },
      borderRadius: {
        sm: "6px",
        md: "8px",
        lg: "12px",
        xl: "16px",
      },
      letterSpacing: {
        tightish: "-0.015em",
        tight:    "-0.02em",
        tighter:  "-0.025em",
      },
      backdropBlur: {
        vibrancy: "20px",
      },
    },
  },
  plugins: [],
};
