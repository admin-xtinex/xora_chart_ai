/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        xora: {
          950: '#0a0e17',
          900: '#0f1520',
          800: '#151c2c',
          700: '#1c2538',
          600: '#243047',
          accent: '#3b82f6',
          green: '#22c55e',
          red: '#ef4444',
          amber: '#f59e0b',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'ui-monospace', 'monospace'],
      },
    },
  },
  plugins: [],
}
