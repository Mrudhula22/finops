/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{js,jsx,ts,tsx}"],
  theme: {
    extend: {
      fontSize: {
        // Bump every size up so nothing looks tiny
        'xs':   ['0.82rem',  { lineHeight: '1.4' }],
        'sm':   ['0.95rem',  { lineHeight: '1.5' }],
        'base': ['1.05rem',  { lineHeight: '1.6' }],
        'lg':   ['1.2rem',   { lineHeight: '1.6' }],
        'xl':   ['1.4rem',   { lineHeight: '1.5' }],
        '2xl':  ['1.6rem',   { lineHeight: '1.4' }],
        '3xl':  ['2rem',     { lineHeight: '1.3' }],
        '4xl':  ['2.5rem',   { lineHeight: '1.2' }],
      },
      colors: {
        primary:  { DEFAULT: "#6366f1", dark: "#4f46e5" },
        success:  "#22c55e",
        warning:  "#f59e0b",
        danger:   "#ef4444",
        aws:      "#FF9900",
        azure:    "#0078D4",
        gcp:      "#4285F4",
      },
    },
  },
  plugins: [],
};
