/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        panel: "#0f172a",
        accent: "#2563eb",
        muted: "#94a3b8"
      },
      fontFamily: {
        sans: ["Segoe UI", "sans-serif"]
      }
    }
  },
  plugins: []
};
