"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { NavItem } from "@/lib/types";

export default function SurfaceNav({ items, 부제 }: { items: NavItem[]; 부제: string }) {
  const pathname = usePathname();
  return (
    <aside style={{ background: "var(--color-accent-900)", color: "var(--color-on-accent)",
      display: "flex", flexDirection: "column", padding: "24px 0" }}>
      <div style={{ padding: "0 20px 22px" }}>
        <Link href="/" style={{ color: "inherit", textDecoration: "none" }}>
          <div style={{ fontFamily: "var(--font-heading)", fontSize: 19, letterSpacing: ".28em", textTransform: "uppercase" }}>
            Secu-Agent
          </div>
        </Link>
        <div style={{ fontSize: 11, letterSpacing: ".1em", color: "var(--color-on-accent-faint)", marginTop: 2 }}>
          {부제}
        </div>
      </div>
      <nav style={{ display: "flex", flexDirection: "column" }}>
        {items.map((item) => {
          const active = pathname.startsWith(item.href);
          return (
            <Link key={item.id} href={item.href}
              style={{ padding: "11px 20px", color: "inherit", textDecoration: "none",
                background: active ? "var(--color-accent-800)" : "transparent",
                display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span style={{ display: "flex", flexDirection: "column", gap: 1 }}>
                <span style={{ fontSize: 14 }}>{item.ko}</span>
                <span style={{ fontSize: 10.5, letterSpacing: ".12em", textTransform: "uppercase", opacity: 0.55 }}>
                  {item.en}
                </span>
              </span>
              <span style={{ fontSize: 10, opacity: 0.5 }}>{item.badge}</span>
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
