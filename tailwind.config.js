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
      },
    },
  },
  plugins: [],
};
