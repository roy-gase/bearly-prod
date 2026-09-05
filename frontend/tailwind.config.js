/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ["class", '[data-theme="dark"]'],
  content: ["./index.html", "./src/**/*.{vue,js}"],
  theme: {
    extend: {
      colors: {
        // Every colour is a CSS variable so light and dark swap in one place.
        page: "var(--page)",
        card: "var(--card)",
        raised: "var(--raised)",
        ink: "var(--ink)",
        "ink-muted": "var(--ink-muted)",
        "ink-subtle": "var(--ink-subtle)",
        line: "var(--line)",
        "line-strong": "var(--line-strong)",
        primary: "var(--primary)",
        "primary-ink": "var(--primary-ink)",
        "primary-soft": "var(--primary-soft)",
        good: "var(--good)",
        "good-ink": "var(--good-ink)",
        warning: "var(--warning)",
        serious: "var(--serious)",
        critical: "var(--critical)",
        "critical-ink": "var(--critical-ink)",
      },
      borderRadius: { lg: "0.625rem", xl: "0.875rem", "2xl": "1.25rem" },
      fontFamily: {
        sans: ['"Space Grotesk"', "system-ui", "-apple-system", '"Segoe UI"', "sans-serif"],
        mono: ['"DM Mono"', "ui-monospace", "SFMono-Regular", "monospace"],
      },
      boxShadow: {
        card: "none",
        pop: "none",
      },
      keyframes: {
        "fade-in": { from: { opacity: 0, transform: "translateY(2px)" }, to: { opacity: 1, transform: "none" } },
      },
      animation: { "fade-in": "fade-in 160ms ease-out" },
    },
  },
  plugins: [],
};
