import type { Config } from 'tailwindcss'

const config: Config = {
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      fontFamily: {
        mono: ['var(--font-mono)', 'monospace'],
        display: ['var(--font-display)', 'serif'],
        body: ['var(--font-body)', 'sans-serif'],
      },
      colors: {
        void: '#edf1f5',
        panel: '#f7f9fb',
        border: '#c7d3df',
        cyan: {
          DEFAULT: '#087582',
          dim: '#176572',
          glow: 'rgba(8,117,130,0.12)',
        },
        amber: {
          sim: '#a85e00',
          'sim-dim': '#814900',
        },
        red: {
          alert: '#bd3f54',
        },
        green: {
          good: '#167a57',
        },
        text: {
          primary: '#1c3042',
          secondary: '#4b6175',
          dim: '#6d8192',
        },
      },
      boxShadow: {
        'cyan-glow': '0 0 18px rgba(8,117,130,0.16), 0 0 42px rgba(8,117,130,0.07)',
        'panel': '0 8px 24px rgba(34,61,82,0.11)',
        'inner-border': 'inset 0 1px 0 rgba(255,255,255,0.7)',
      },
      animation: {
        'pulse-slow': 'pulse 3s ease-in-out infinite',
        'scan': 'scan 4s linear infinite',
        'fade-in': 'fadeIn 0.4s ease forwards',
        'slide-up': 'slideUp 0.5s ease forwards',
      },
      keyframes: {
        scan: {
          '0%': { transform: 'translateY(-100%)' },
          '100%': { transform: 'translateY(100vh)' },
        },
        fadeIn: {
          from: { opacity: '0' },
          to: { opacity: '1' },
        },
        slideUp: {
          from: { opacity: '0', transform: 'translateY(16px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
      },
    },
  },
  plugins: [],
}
export default config
