"use client";

import { usePathname } from "next/navigation";
import { NAV_ITEMS } from "@/lib/types";
import type { Role } from "@/lib/session";

// signOutAction 은 서버 액션(frontend/auth.ts)이라 클라이언트 컴포넌트가
// 직접 import 할 수 없다 — 이 컴포넌트를 렌더하는 서버 컴포넌트가 prop 으로
// 내려준다.
export default function Header({
  email,
  role,
  signOutAction,
}: {
  email: string;
  role: Role;
  signOutAction: () => Promise<void>;
}) {
  const pathname = usePathname();
  const current =
    NAV_ITEMS.find((item) => (item.href === "/" ? pathname === "/" : pathname.startsWith(item.href))) ??
    NAV_ITEMS[0];

  return (
    <header
      style={{
        display: "flex",
        alignItems: "flex-end",
        gap: 20,
        padding: "26px 40px 18px",
        borderBottom: "1px solid var(--color-divider)",
      }}
    >
      <div style={{ flex: 1, minWidth: 0 }}>
        <div
          style={{
            fontSize: 10.5,
            letterSpacing: ".18em",
            textTransform: "uppercase",
            color: "var(--color-accent)",
          }}
        >
          {current.en}
        </div>
        <h1 style={{ margin: "3px 0 0", fontSize: 30, lineHeight: 1.1 }}>{current.ko}</h1>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
        <div style={{ textAlign: "right", lineHeight: 1.3 }}>
          <div style={{ fontSize: 13 }}>{email}</div>
          <div style={{ fontSize: 11, color: "var(--color-neutral-600)" }}>
            {role === "admin" ? "Google OAuth · 관리자 세션" : "Google OAuth · 일반 사용자"}
          </div>
        </div>
        <form action={signOutAction}>
          <button className="btn btn-secondary" type="submit">
            로그아웃 / Sign out
          </button>
        </form>
      </div>
    </header>
  );
}
