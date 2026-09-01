"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { NAV_ITEMS, type HealthzResponse } from "@/lib/types";
import type { Role } from "@/lib/session";

export default function Sidebar({ role }: { role: Role }) {
  const pathname = usePathname();
  // 관리자 항목은 role !== "admin" 이면 배열에서 아예 빠진다(숨김이 아니라 미포함).
  const items = NAV_ITEMS.filter((item) => !item.adminOnly || role === "admin");

  return (
    <aside
      style={{
        background: "var(--color-accent-900)",
        color: "var(--color-on-accent)",
        display: "flex",
        flexDirection: "column",
        padding: "24px 0",
      }}
    >
      <div style={{ padding: "0 20px 22px" }}>
        <div
          style={{
            fontFamily: "var(--font-heading)",
            fontSize: 19,
            letterSpacing: ".28em",
            textTransform: "uppercase",
          }}
        >
          Secu-Agent
        </div>
        <div style={{ fontSize: 11, letterSpacing: ".1em", color: "var(--color-on-accent-faint)", marginTop: 2 }}>
          사내 보안 규정 에이전트
        </div>
      </div>
      <nav style={{ display: "flex", flexDirection: "column" }}>
        {items.map((item) => {
          const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
          return (
            <Link key={item.id} href={item.href} style={navStyle(active)}>
              <span style={{ display: "flex", flexDirection: "column", alignItems: "flex-start", gap: 1 }}>
                <span style={{ fontSize: 14 }}>{item.ko}</span>
                <span
                  style={{ fontSize: 10.5, letterSpacing: ".12em", textTransform: "uppercase", opacity: 0.55 }}
                >
                  {item.en}
                </span>
              </span>
              <span style={{ fontSize: 10, opacity: 0.5 }}>{item.badge}</span>
            </Link>
          );
        })}
      </nav>
      <HealthzBlock />
    </aside>
  );
}

function navStyle(active: boolean): React.CSSProperties {
  return {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 8,
    width: "100%",
    padding: "11px 20px",
    background: active ? "var(--color-on-accent-wash)" : "transparent",
    borderLeft: active ? "3px solid var(--color-accent-300)" : "3px solid transparent",
    color: active ? "var(--color-on-accent-strong)" : "var(--color-on-accent-dim)",
    textDecoration: "none",
    fontFamily: "var(--font-body)",
  };
}

// GET /healthz 를 BFF 경유로 실제 호출한다 — 지어낸 "db true · model ready"
// 를 적지 않는다.
function HealthzBlock() {
  const [health, setHealth] = useState<HealthzResponse | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetch("/api/healthz")
      .then((r) => {
        if (!r.ok) throw new Error(`healthz ${r.status}`);
        return r.json() as Promise<HealthzResponse>;
      })
      .then((data) => {
        if (!cancelled) setHealth(data);
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div
      style={{
        marginTop: "auto",
        padding: 20,
        borderTop: "1px solid var(--color-on-accent-divider)",
        display: "flex",
        flexDirection: "column",
        gap: 8,
      }}
    >
      <div style={{ fontSize: 10, letterSpacing: ".16em", textTransform: "uppercase", color: "var(--color-on-accent-faint)" }}>
        GET /healthz
      </div>
      {failed ? (
        <div style={{ fontSize: 12.5, color: "var(--color-on-accent-danger)" }}>연결 실패 / unreachable</div>
      ) : !health ? (
        <div style={{ fontSize: 12.5, color: "var(--color-on-accent-muted)" }}>확인 중… / checking…</div>
      ) : (
        <>
          <HealthzRow label="db" value={String(health.db)} accent />
          <HealthzRow label="model" value={health.model} accent />
          <HealthzRow label="status" value={health.status} />
        </>
      )}
    </div>
  );
}

function HealthzRow({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12.5 }}>
      <span style={{ color: "var(--color-on-accent-muted)" }}>{label}</span>
      <span style={accent ? { color: "var(--color-on-accent-ok)" } : undefined}>{value}</span>
    </div>
  );
}
