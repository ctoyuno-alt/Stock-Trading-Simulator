/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        obsidian: {
          950: '#06090E',
          900: '#080B11',
          850: '#0B0F17',
          800: '#0E131F',
          750: '#121827',
          700: '#161D2F',
        },
        border: {
          subtle: 'rgba(255, 255, 255, 0.07)',
          medium: '#1E2638',
          accent: '#2A364F',
        },
        bloomberg: {
          amber: '#FF9900',
          orange: '#FF7700',
        },
        neon: {
          green: '#00E676',
          emerald: '#10B981',
          red: '#FF3366',
          rose: '#F43F5E',
          cyan: '#00F2FE',
          blue: '#38BDF8',
          purple: '#A855F7',
        }
      },
      fontFamily: {
        sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'Menlo', 'monospace'],
      },
      animation: {
        'ticker-scroll': 'ticker 38s linear infinite',
      },
      keyframes: {
        ticker: {
          '0%': { transform: 'translateX(0)' },
          '100%': { transform: 'translateX(-50%)' },
        }
      }
    },
  },
  plugins: [],
}
