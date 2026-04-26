/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/net_alpha/web/templates/**/*.html",
  ],
  theme: {
    extend: {
      fontFamily: {
        mono: ["Fira Code", "ui-monospace", "monospace"],
        sans: ["Fira Sans", "ui-sans-serif", "system-ui"],
      },
    },
  },
  plugins: [],
}
