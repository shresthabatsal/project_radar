import type { Config } from "tailwindcss";

// Brand primary #009258, expanded into a 50-950 shade scale (500 == the
// brand color itself, HSL ~156.2°, 100%, 28.6%). Tints (50-400) are mixed
// toward white and shades (600-950) toward black in RGB space, rather than
// a constant/scaled-saturation HSL lightness sweep - at S=100 the latter
// clips into neon at high lightness (mixing toward white naturally
// desaturates, which is what makes a tint read as a soft pastel instead).
const primary = {
  50: "#f2faf7",
  100: "#def1e9",
  200: "#b5dfcf",
  300: "#85cbaf",
  400: "#47b187",
  500: "#009258",
  600: "#007e4c",
  700: "#00663e",
  800: "#004f30",
  900: "#003a23",
  950: "#002617",
};

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        primary,
      },
      fontFamily: {
        display: ["var(--font-display)"],
        sans: ["var(--font-sans)"],
      },
    },
  },
  plugins: [],
};

export default config;
