/** @type {import('tailwindcss').Config} */
// Tailwind colours map to CSS variables defined in src/index.css. This
// is the magic that makes accessibility classes (text-l/text-xl/
// high-contrast) reflow the entire UI by re-binding the variables.

export default {
  content: ['./index.html', './src/**/*.{ts,tsx,js,jsx}'],
  theme: {
    extend: {
      fontFamily: {
        wordmark: ['var(--font-wordmark)'],
        display: ['var(--font-display)'],
        sans: ['var(--font-sans)'],
        mono: ['var(--font-mono)'],
      },
      colors: {
        bg:      'var(--bg)',
        'bg-soft': 'var(--bg-soft)',
        'bg-sunk': 'var(--bg-sunk)',
        'bg-tint': 'var(--bg-tint)',

        line:        'var(--line)',
        'line-strong': 'var(--line-strong)',

        ink:         'var(--ink)',
        'ink-muted': 'var(--ink-muted)',
        'ink-soft':  'var(--ink-soft)',
        'ink-faint': 'var(--ink-faint)',
        'ink-on':    'var(--ink-on-color)',

        primary:        'var(--primary)',
        'primary-hover':'var(--primary-hover)',
        'primary-soft': 'var(--primary-soft)',
        success:        'var(--success)',
        'success-soft': 'var(--success-soft)',
        danger:         'var(--danger)',
        'danger-soft':  'var(--danger-soft)',
        warning:        'var(--warning)',
        'warning-soft': 'var(--warning-soft)',
        neutral:        'var(--neutral)',
        'neutral-soft': 'var(--neutral-soft)',
      },
      fontSize: {
        xs:   'var(--fs-xs)',
        sm:   'var(--fs-sm)',
        base: 'var(--fs-base)',
        md:   'var(--fs-md)',
        lg:   'var(--fs-lg)',
        xl:   'var(--fs-xl)',
        '2xl':'var(--fs-2xl)',
        '3xl':'var(--fs-3xl)',
      },
      borderRadius: {
        sm: 'var(--r-sm)',
        md: 'var(--r-md)',
        lg: 'var(--r-lg)',
        xl: 'var(--r-xl)',
      },
      boxShadow: {
        1: 'var(--shadow-1)',
        2: 'var(--shadow-2)',
        3: 'var(--shadow-3)',
      },
    },
  },
  plugins: [],
}
