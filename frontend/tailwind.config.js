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
        // XTinex-inspired colors for brand continuity
        'xtinex-black': '#02030a',
        'xtinex-void': '#03040a',
        'xtinex-ink': '#070814',
        'xtinex-fg': '#eef1f7',
        'xtinex-muted': '#b4bccb',
        'xtinex-faint': '#5c6478',
        'xtinex-cyan': '#3ecbff',
        'xtinex-blue': '#4f8ef7',
        'xtinex-violet': '#a855f7',
        'xtinex-magenta': '#d946ef',
        'xtinex-gold': '#e8b86d',
        'xtinex-line': 'rgba(238, 241, 247, 0.12)',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'ui-monospace', 'monospace'],
        // XTinex fonts for brand continuity
        display: ['Outfit', 'Manrope', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        body: ['Manrope', 'ui-sans-serif', 'system-ui', 'sans-serif'],
      },
      boxShadow: {
        glow: '0 0 35px rgba(79, 140, 255, 0.16)',
      },
    },
  },
  plugins: [],
}
