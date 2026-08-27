/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        xora: {
          950: '#050810',
          900: '#0a101b',
          800: '#101827',
          700: '#172235',
          600: '#24334d',
          accent: '#4f8cff',
          cyan: '#5ee7f7',
          green: '#22c55e',
          red: '#ef4444',
          amber: '#f59e0b',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'ui-monospace', 'monospace'],
      },
      boxShadow: {
        glow: '0 0 35px rgba(79, 140, 255, 0.16)',
      },
    },
  },
  plugins: [],
}
