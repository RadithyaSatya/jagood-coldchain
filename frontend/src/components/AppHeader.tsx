"use client";

import Image from "next/image";
import { useEffect, useState } from "react";

const navigation = [
  { href: "#planner", label: "Perencanaan Rute" },
  { href: "#hasil-rute", label: "Hasil Rute" },
  { href: "#simulasi", label: "Simulasi Skenario" },
];

export default function AppHeader() {
  const [activeHref, setActiveHref] = useState("#planner");

  useEffect(() => {
    function syncActiveNavigation() {
      const hash = window.location.hash;
      if (navigation.some((item) => item.href === hash)) setActiveHref(hash);
    }

    syncActiveNavigation();
    window.addEventListener("hashchange", syncActiveNavigation);
    return () => window.removeEventListener("hashchange", syncActiveNavigation);
  }, []);

  return (
    <header className="app-header">
      <div className="app-header__inner">
        <a className="app-header__brand" href="#planner" aria-label="JaGOOD Smart Route Planner">
          <Image src="/brand/jagood.png" alt="JaGOOD" width={184} height={45} priority />
        </a>
        <nav className="app-header__nav" aria-label="Navigasi utama">
          {navigation.map((item) => (
            <a
              key={item.href}
              href={item.href}
              aria-current={activeHref === item.href ? "page" : undefined}
              onClick={() => setActiveHref(item.href)}
            >
              {item.label}
            </a>
          ))}
        </nav>
      </div>
    </header>
  );
}
