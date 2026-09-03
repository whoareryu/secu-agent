"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { NavItem } from "@/lib/types";
import HealthzBlock from "./HealthzBlock";

// healthz: 백엔드 상태 readout 을 보일지는 면마다 다르다. 직원 면은 이미
// 레이아웃 단에서 principals() 실패를 전체 화면 카드로 잡는다(app/(employee)/layout.tsx)
// — 백엔드가 없으면 애초에 SurfaceNav 까지 렌더되지 않으니 여기 readout이
// 군더더기다. 설명 면은 다르다 — /documents · /principals 가 각자 fetch 하고,
// /how 의 패널 ①(LeakCompare)도 눌렀을 때 실제로 백엔드를 부른다. 이 배포가
// 상시 가동이 아니라는 사실(app/page.tsx 참조)을 감안하면, 세 화면 모두
// 조용히 실패하기 전에 "백엔드가 꺼져 있다"를 미리 알려주는 것이 소음이
// 아니라 근거다. 그래서 설명 면 레이아웃만 healthz 를 켠다.
export default function SurfaceNav({
  items,
  부제,
  healthz,
}: {
  items: NavItem[];
  부제: string;
  healthz?: boolean;
}) {
  const pathname = usePathname();
  return (
    <aside className="surface-nav">
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
      <nav className="surface-nav-list">
        {items.map((item) => {
          const active = pathname.startsWith(item.href);
          return (
            <Link key={item.id} href={item.href} aria-current={active ? "page" : undefined}
              className="surface-nav-item">
              <span style={{ display: "flex", flexDirection: "column", gap: 1 }}>
                <span style={{ fontSize: 14 }}>{item.ko}</span>
                <span className="surface-nav-sub">{item.en}</span>
              </span>
              <span style={{ fontSize: 10, opacity: 0.5 }}>{item.badge}</span>
            </Link>
          );
        })}
      </nav>
      {healthz ? <HealthzBlock /> : null}
    </aside>
  );
}
