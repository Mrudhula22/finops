/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{js,jsx,ts,tsx}"],
  theme: {
    extend: {
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
