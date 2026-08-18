"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ThemeToggle } from "@/components/ThemeToggle";

const NAV_LINKS = [
  { href: "/search", label: "Advanced Search" },
  { href: "/teams", label: "Squad Profiles" },
];

export function Header() {
  const pathname = usePathname();
  // The admin utility panel is deliberately unbranded (see app/admin) - no
  // logo, no marketing nav - so it reads as a distinct, plain surface.
  if (pathname?.startsWith("/admin")) return null;

  return (
    <header className="border-b border-primary-100 bg-white dark:border-primary-900 dark:bg-[#0b110f]">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 sm:px-6">
        <Link href="/" className="flex items-center gap-2 transition-opacity hover:opacity-80">
          <Image
            src="/brand/radar_main_primary.png"
            alt="Radar"
            width={140}
            height={32}
            priority
            className="h-8 w-auto dark:hidden"
          />
          <Image
            src="/brand/radar_main_white.png"
            alt="Radar"
            width={140}
            height={32}
            priority
            className="hidden h-8 w-auto dark:block"
          />
        </Link>

        <nav className="flex items-center gap-6">
          {NAV_LINKS.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className="font-sans text-sm font-medium text-foreground/70 transition hover:text-primary-600 dark:hover:text-primary-400"
            >
              {link.label}
            </Link>
          ))}
          <ThemeToggle />
        </nav>
      </div>
    </header>
  );
}
