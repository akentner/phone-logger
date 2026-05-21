import type { Config } from 'tailwindcss'

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        ha: {
          bg: '#111827',
          surface: '#1f2937',
          border: '#374151',
          text: '#f9fafb',
          muted: '#9ca3af',
          accent: '#3b82f6',
        },
      },
    },
  },
  plugins: [],
} satisfies Config
