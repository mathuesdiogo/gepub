/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        primary: {
          DEFAULT: '#2468d6',
          foreground: '#f8fbff',
        },
      },
      boxShadow: {
        panel: '0 20px 55px rgba(19, 42, 88, 0.16)',
      },
      borderRadius: {
        xl2: '1.1rem',
      },
    },
  },
  plugins: [],
}
