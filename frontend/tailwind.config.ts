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
        void: '#080c12',
        panel: '#0d1420',
        border: '#1a2535',
        cyan: {
          DEFAULT: '#00e5ff',
          dim: '#0099bb',
          glow: 'rgba(0,229,255,0.15)',
        },
        amber: {
          sim: '#ffaa00',
          'sim-dim': '#cc8800',
        },
        red: {
          alert: '#ff3b5c',
        },
        green: {
          good: '#00e5a0',
        },
        text: {
          primary: '#e8f0fe',
          secondary: '#6b7fa3',
          dim: '#3a4d6b',
        },
      },
      boxShadow: {
        'cyan-glow': '0 0 20px rgba(0,229,255,0.3), 0 0 60px rgba(0,229,255,0.1)',
        'panel': '0 4px 24px rgba(0,0,0,0.6)',
        'inner-border': 'inset 0 1px 0 rgba(255,255,255,0.05)',
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
