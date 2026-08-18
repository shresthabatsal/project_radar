import { Space_Grotesk, Inter } from "next/font/google";

// Headings / display text: geometric, technical - matches Radar's data/HUD branding.
export const spaceGrotesk = Space_Grotesk({
  subsets: ["latin"],
  weight: ["500", "600", "700"],
  variable: "--font-display",
  display: "swap",
});

// Body / UI / data-table text: legible at small sizes.
export const inter = Inter({
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap",
});
