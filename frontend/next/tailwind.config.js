/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/**/*.{ts,tsx}",
    "./src/app/**/*.{ts,tsx}",
    "./src/components/**/*.{ts,tsx}"
  ],
  theme: {
    extend: {
      colors: {
        background: "#0a0a0f",
        card: "#12121a",
        border: "#1e1e2e",
        primary: "#22c55e",
        danger: "#ef4444",
        warning: "#f59e0b",
        accent: "#8b5cf6",
        info: "#3b82f6",
        textMain: "#ffffff",
        textSecondary: "#71717a"
      },
      boxShadow: {
        soft: "0 4px 12px rgba(0,0,0,0.25)"
      },
      borderRadius: {
        xl: "1rem"
      }
    }
  },
  plugins: []
}
