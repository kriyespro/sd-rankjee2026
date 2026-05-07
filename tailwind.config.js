/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./templates/**/*.jinja'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        heading: ['Outfit', 'ui-sans-serif', 'system-ui', 'sans-serif'],
      },
      colors: {
        primary: '#4f46e5',
        'primary-dark': '#4338ca',
        /* RankJee brand — keep named tokens so compiled CSS always includes earnings/marketing surfaces */
        'rj-navy': '#0D2B5E',
        'rj-gold': '#F5B731',
        'rj-saffron': '#F4711C',
        'rj-wa': '#25D366',
      },
    },
  },
  plugins: [],
};
