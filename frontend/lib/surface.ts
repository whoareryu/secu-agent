import type { NavItem } from "./types.ts";

// 역할은 서버가 준다 — GET /principals 응답의 role 이다. 여기에 이름→역할
// 맵을 두지 않는다: 그러면 권한 판정의 네 번째 사본이 되고, 이 프로젝트가
// 스스로 경고한 함정이다(스펙 §2.1).
export type Role = "member" | "auditor" | "developer";

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

// 면에 들어갈 수 있는지 판정한다. 로그인은 더 이상 어느 면의 조건도 아니다 —
// 로그인 벽이 남은 자리는 유료 LLM 을 부르는 /ask 의 제출 하나뿐이다(스펙
// §2.3). "to-login" 은 그래서 여기서 나오지 않고, 호출부가 그 제출 시점에
// 쓰는 값으로 남는다.
export function guard(input: {
  surface: Surface;
  hasPersona: boolean;
  role: Role;
}): "ok" | "to-hub" | "to-login" {
  // 관리자 면은 감사 역할만. 역할은 페르소나에서 오므로 페르소나가 없으면
  // 판정할 근거 자체가 없다.
  if (input.surface === "admin" && (!input.hasPersona || input.role !== "auditor")) {
    return "to-hub";
  }
  if (input.surface === "employee" && !input.hasPersona) return "to-hub";
  return "ok";
}
