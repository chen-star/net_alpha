/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/net_alpha/web/templates/**/*.html",
  ],
  safelist: [
    { pattern: /^bg-(primary|secondary|accent|bg|confirmed|probable|unclear)$/ },
    { pattern: /^text-(primary|secondary|accent|bg|ink|confirmed|probable|unclear)$/ },
    { pattern: /^border-(primary|secondary|accent|confirmed|probable|unclear)$/ },
    "hover:bg-secondary",
    "hover:bg-slate-50",
    "btn",
    "btn-ghost",
    "kpi-card",
    "row-hover",
    "badge-confirmed",
    "badge-probable",
    "badge-unclear",
  ],
  theme: {
    extend: {
      fontFamily: {
        mono: ["Fira Code", "ui-monospace", "monospace"],
        sans: ["Fira Sans", "ui-sans-serif", "system-ui"],
      },
      colors: {
        primary: "#1e3a8a",     // dark blue
        secondary: "#1e40af",   // lighter blue (hover state)
        accent: "#0ea5e9",      // cyan
        bg: "#f1f5f9",          // slate-100
        ink: "#0f172a",         // slate-900
        confirmed: "#dc2626",   // red-600
        probable: "#f59e0b",    // amber-500
        unclear: "#3b82f6",     // blue-500
      },
    },
  },
  plugins: [],
}
