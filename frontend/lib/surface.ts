import type { Role } from "./session.ts";
import type { NavItem } from "./types.ts";

// 화면을 네 면으로 나눈다. 허브는 면이 아니라 그 셋으로 들어가는 입구라
// 여기 없다.
export type Surface = "employee" | "explain" | "admin";

const NAV: Record<Surface, NavItem[]> = {
  employee: [
    { id: "ask", ko: "질의", en: "Ask", badge: "", href: "/ask", adminOnly: false },
    { id: "my-docs", ko: "내 문서", en: "My documents", badge: "", href: "/my/documents", adminOnly: false },
  ],
  explain: [
    { id: "how", ko: "동작 원리", en: "How it works", badge: "", href: "/how", adminOnly: false },
    { id: "docs", ko: "문서 가시성", en: "Visibility", badge: "", href: "/documents", adminOnly: false },
    { id: "principals", ko: "계정", en: "Principals", badge: "", href: "/principals", adminOnly: false },
  ],
  admin: [
    { id: "logs", ko: "감사 로그", en: "Audit log", badge: "ADMIN", href: "/logs", adminOnly: true },
    { id: "admin", ko: "관리자 대시보드", en: "Admin", badge: "ADMIN", href: "/admin", adminOnly: true },
  ],
};

export function navFor(surface: Surface): NavItem[] {
  return NAV[surface];
}

// 면에 들어갈 수 있는지 판정한다. 세션 확인은 각 레이아웃이 이미 하므로
// 여기서는 세션이 있다고 본다 — "to-login" 은 그 판정이 이 함수로 옮겨올
// 날을 위해 남겨둔 값이 아니라, 호출부가 세션 없음을 알았을 때 쓰는 값이다.
export function guard(input: {
  surface: Surface;
  hasPersona: boolean;
  role: Role;
}): "ok" | "to-hub" | "to-login" {
  if (input.surface === "admin" && input.role !== "admin") return "to-hub";
  if (input.surface === "employee" && !input.hasPersona) return "to-hub";
  return "ok";
}
