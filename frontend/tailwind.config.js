/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        mono: ['"IBM Plex Mono"', 'monospace'],
        code: ['"JetBrains Mono"', 'monospace'],
      },
      colors: {
        bg: {
          base:     '#080c12',
          surface:  '#0d1117',
          elevated: '#161b22',
          input:    '#0d1117',
        },
        border: {
          DEFAULT: '#21262d',
          subtle:  '#161b22',
        },
        text: {
          primary:   '#e6edf3',
          secondary: '#8b949e',
          muted:     '#484f58',
        },
        accent: '#58a6ff',
        status: {
          queued:     '#388bfd',
          processing: '#d29922',
          completed:  '#3fb950',
          failed:     '#f85149',
          cancelled:  '#484f58',
        },
        priority: {
          high:   '#f85149',
          medium: '#d29922',
          low:    '#484f58',
        },
        log: {
          info:    '#388bfd',
          warning: '#d29922',
          error:   '#f85149',
          debug:   '#484f58',
        },
      },
      keyframes: {
        'pulse-dot': {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.2' },
        },
        'slide-in': {
          from: { transform: 'translateX(110%)', opacity: '0' },
          to:   { transform: 'translateX(0)',    opacity: '1' },
        },
      },
      animation: {
        'pulse-dot': 'pulse-dot 1.5s ease-in-out infinite',
        'slide-in':  'slide-in 0.25s ease-out',
      },
    },
  },
  plugins: [],
}
