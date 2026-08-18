import type { Metadata } from "next";
import Script from "next/script";
import "./globals.css";
import { spaceGrotesk, inter } from "@/lib/fonts";
import { Header } from "@/components/Header";

// Applies a stored dark-mode choice (if any) to <html> before hydration, so
// there's no flash between a theme-less server render and the corrected
// client theme. Absence of a stored value is deliberately a no-op - new
// visitors stay on the default light markup rather than falling back to
// prefers-color-scheme, per ThemeToggle's contract.
const THEME_INIT_SCRIPT = `
try {
  if (localStorage.getItem('radar-theme') === 'dark') {
    document.documentElement.classList.add('dark');
  }
} catch (e) {}
`;

export const metadata: Metadata = {
  title: "Radar",
  description:
    "Football scouting decision-support: player profiles, similarity search, hidden gems, market value, moneyball.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${spaceGrotesk.variable} ${inter.variable} h-full antialiased`}
      // The theme-init script (below) adds/omits the "dark" class on this
      // element before hydration runs, based on localStorage - a legitimate,
      // expected difference from the server-rendered (always theme-less)
      // markup, not a real bug. suppressHydrationWarning is the documented
      // escape hatch for exactly this pattern (see next-themes' own approach).
      suppressHydrationWarning
    >
      <body className="flex min-h-full flex-col font-sans">
        <Script id="theme-init" strategy="beforeInteractive">
          {THEME_INIT_SCRIPT}
        </Script>
        <Header />
        <main className="flex-1">{children}</main>
      </body>
    </html>
  );
}
