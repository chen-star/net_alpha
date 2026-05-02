/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/net_alpha/web/templates/**/*.html"],
  safelist: [
    // semantic colors used dynamically in templates
    { pattern: /^bg-(surface|surface-2|surface-3|pos|neg|warn|info|indigo|violet|overlay-strong|overlay-medium|overlay-soft|row-hover|topbar-bg|cash|pos-tint|neg-tint|warn-tint|info-tint|indigo-tint|violet-tint|skeleton)$/ },
    { pattern: /^text-(label-1|label-2|label-3|pos|neg|warn|info|indigo|violet|text)$/ },
    { pattern: /^border-(hairline|hairline-strong|pos|neg|warn|info|indigo|violet|indigo-edge|text)$/ },
    // chip variants
    "chip", "chip-confirm", "chip-probable", "chip-unclear",
    // KPI hero halo
    "kpi-hero",
    // segmented buttons
    "seg", "seg-active",
    // mono-icon helper
    "icon-mono",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['-apple-system', '"SF Pro Display"', '"Inter"', 'system-ui', 'sans-serif'],
        mono: ['"SF Mono"', '"JetBrains Mono"', 'ui-monospace', 'Menlo', 'monospace'],
      },
      colors: {
        // All values resolve through CSS custom properties so [data-theme="…"]
        // overrides take effect at runtime. Hex/rgba fallbacks would defeat
        // theme switching.
        bg:            "var(--color-bg)",
        surface:       "var(--color-surface)",
        "surface-2":   "var(--color-surface-2)",
        "surface-3":   "var(--color-surface-3)",
        hairline:        "var(--color-hairline)",
        "hairline-strong": "var(--color-hairline-strong)",
        text:      "var(--color-text)",
        "label-1": "var(--color-label-1)",
        "label-2": "var(--color-label-2)",
        "label-3": "var(--color-label-3)",
        indigo:  "var(--color-indigo)",
        violet:  "var(--color-violet)",
        pos:    "var(--color-pos)",
        neg:    "var(--color-neg)",
        warn:   "var(--color-warn)",
        info:   "var(--color-info)",
        // Allocation rank palette (slot-bound)
        "rank-1":  "var(--color-rank-1)",
        "rank-2":  "var(--color-rank-2)",
        "rank-3":  "var(--color-rank-3)",
        "rank-4":  "var(--color-rank-4)",
        "rank-5":  "var(--color-rank-5)",
        "rank-6":  "var(--color-rank-6)",
        "rank-7":  "var(--color-rank-7)",
        "rank-8":  "var(--color-rank-8)",
        "rank-9":  "var(--color-rank-9)",
        "rank-10": "var(--color-rank-10)",
        "rank-rest": "var(--color-rank-rest)",
        // Theme-flexible additions
        "overlay-strong": "var(--color-overlay-strong)",
        "overlay-medium": "var(--color-overlay-medium)",
        "overlay-soft":   "var(--color-overlay-soft)",
        "row-hover":      "var(--color-row-hover)",
        "topbar-bg":      "var(--color-topbar-bg)",
        "brand-glow":     "var(--color-brand-glow)",
        cash:             "var(--color-cash)",
        "pos-tint":       "var(--color-pos-tint)",
        "neg-tint":       "var(--color-neg-tint)",
        "warn-tint":      "var(--color-warn-tint)",
        "info-tint":      "var(--color-info-tint)",
        "indigo-tint":    "var(--color-indigo-tint)",
        "violet-tint":    "var(--color-violet-tint)",
        "indigo-edge":    "var(--color-indigo-edge)",
        skeleton:         "var(--color-skeleton)",
        // Back-compat aliases for existing class refs (badge-confirmed etc.)
        confirmed: "var(--color-confirmed)",
        probable:  "var(--color-probable)",
        unclear:   "var(--color-unclear)",
        primary:   "var(--color-primary)",
        secondary: "var(--color-secondary)",
        accent:    "var(--color-accent)",
        ink:       "var(--color-ink)",
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
