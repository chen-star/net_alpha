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
        primary: "#1E40AF",
        secondary: "#3B82F6",
        accent: "#F59E0B",
        bg: "#F8FAFC",
        ink: "#0F172A",
        confirmed: "#DC2626",
        probable: "#F59E0B",
        unclear: "#3B82F6",
      },
    },
  },
  plugins: [],
}
