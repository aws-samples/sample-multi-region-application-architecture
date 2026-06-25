/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        surface: {
          DEFAULT: '#0f172a',
          card: '#1e293b',
          hover: '#334155',
        },
        accent: {
          DEFAULT: '#38bdf8',
          dim: '#0ea5e9',
        },
        status: {
          green: '#4ade80',
          yellow: '#facc15',
          red: '#f87171',
          orange: '#fb923c',
        },
      },
    },
  },
  plugins: [],
}
