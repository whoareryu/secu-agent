"use client";

import { usePathname } from "next/navigation";
import type { NavItem } from "@/lib/types";

// signInAction · signOutAction 은 서버 액션(frontend/auth.ts)이라 클라이언트
// 컴포넌트가 직접 import 할 수 없다 — 이 컴포넌트를 렌더하는 서버 컴포넌트가
// prop 으로 내려준다.
//
// items 를 prop 으로 받는다 — 항목 배열을 여기서 직접 import 하면 면마다
// 다른 배열(lib/surface.ts 의 navFor)을 쓸 수 없다. 전역 NAV_ITEMS 상수는
// 그 navFor 로 대체되어 이제 없다.
//
// role 을 받지 않는다. 헤더가 "관리자 세션" 이라 적던 근거는 이메일
// 알리스트였는데 그것이 사라졌고(스펙 §2.5), 지금 이 면에 서 있다는 사실이
// 이미 역할을 말한다 — 헤더가 그것을 한 번 더, 다른 근거로 주장하면
// 두 벌이 된다.
export default function Header({
  email,
  signInAction,
  signOutAction,
  items,
}: {
  email: string | null;
  signInAction: () => Promise<void>;
  signOutAction: () => Promise<void>;
  items: NavItem[];
}) {
  const pathname = usePathname();
  const current =
    items.find((item) => (item.href === "/" ? pathname === "/" : pathname.startsWith(item.href))) ?? items[0];

  return (
    <header
      style={{
        display: "flex",
        alignItems: "flex-end",
        gap: 20,
        padding: "26px 40px 18px",
        background: "var(--color-surface)",
        borderBottom: "1px solid var(--color-divider)",
      }}
    >
      <div style={{ flex: 1, minWidth: 0 }}>
        <div
          style={{
            fontSize: 13,
            fontWeight: 700,
            letterSpacing: 0,
            color: "var(--color-accent)",
          }}
        >
          {current.en}
        </div>
        <h1 style={{ margin: "3px 0 0", fontSize: 30, lineHeight: 1.1 }}>{current.ko}</h1>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
        {email ? (
          <>
            <div style={{ textAlign: "right", lineHeight: 1.3 }}>
              <div style={{ fontSize: 13 }}>{email}</div>
              <div style={{ fontSize: 11, color: "var(--color-neutral-600)" }}>Google OAuth 세션</div>
            </div>
            <form action={signOutAction}>
              <button className="btn btn-secondary" type="submit">
                로그아웃 / Sign out
              </button>
            </form>
          </>
        ) : (
          <form action={signInAction}>
            <button className="btn btn-secondary" type="submit">
              로그인 / Sign in
            </button>
          </form>
        )}
      </div>
    </header>
  );
}
