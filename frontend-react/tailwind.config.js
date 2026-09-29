/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
      },
      colors: {
        // Design token bridge — all CSS-var driven
        background:          'var(--background)',
        foreground:          'var(--foreground)',
        card:                'var(--card)',
        'card-foreground':   'var(--card-foreground)',
        popover:             'var(--popover)',
        'popover-foreground':'var(--popover-foreground)',
        primary:             'var(--primary)',
        'primary-foreground':'var(--primary-foreground)',
        secondary:           'var(--secondary)',
        'secondary-foreground':'var(--secondary-foreground)',
        muted:               'var(--muted)',
        'muted-foreground':  'var(--muted-foreground)',
        accent:              'var(--accent)',
        'accent-foreground': 'var(--accent-foreground)',
        destructive:         'var(--destructive)',
        'destructive-foreground':'var(--destructive-foreground)',
        border:              'var(--border)',
        input:               'var(--input)',
        ring:                'var(--ring)',
        // Sidebar tokens
        sidebar: {
          DEFAULT:  'var(--sidebar-bg)',
          border:   'var(--sidebar-border)',
          text:     'var(--sidebar-text)',
          muted:    'var(--sidebar-text-muted)',
          active:   'var(--sidebar-active-bg)',
          hover:    'var(--sidebar-hover-bg)',
        },
      },
      borderRadius: {
        DEFAULT: 'var(--radius)',
        sm: 'calc(var(--radius) - 2px)',
        lg: 'calc(var(--radius) + 2px)',
        xl: 'calc(var(--radius) + 4px)',
      },
      boxShadow: {
        card:  '0 1px 3px 0 rgb(0 0 0 / 0.06), 0 1px 2px -1px rgb(0 0 0 / 0.06)',
        panel: '0 1px 4px 0 rgb(0 0 0 / 0.08)',
        dropdown: '0 4px 12px 0 rgb(0 0 0 / 0.12)',
        modal: '0 20px 60px 0 rgb(0 0 0 / 0.18)',
      },
    },
  },
  plugins: [],
}
