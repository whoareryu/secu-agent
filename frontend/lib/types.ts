// GET /healthz (BFF 를 거쳐 백엔드가 그대로 돌려주는 값) — backend/api/main.py 의 healthz() 참조.
export type HealthzResponse = {
  status: string;
  db: boolean;
  model: string;
};

// 열람 기록을 한 번에 가져오는 최대 행 수. 백엔드 GET /access-log 의
// limit 상한(backend/api/main.py 의 `le=200`)과 같은 값이다 — 더 크게
// 불러도 백엔드가 422 로 거절한다.
//
// 받은 행이 정확히 이 값이면 그 위에 더 있을 수 있다. 그때 화면이 "전체"
// 라고 적으면 거짓이 된다. 전역 집계용 COUNT 엔드포인트는 만들지 않고,
// 화면이 자기가 아는 만큼만 주장하게 한다.
export const LOG_LIMIT = 200;

// 앱 셸의 사이드바 메뉴 · 헤더 제목이 함께 참조하는 화면 메타데이터.
export type NavItem = {
  id: string;
  ko: string;
  en: string;
  badge: string;
  href: string;
  adminOnly: boolean;
};

export const NAV_ITEMS: NavItem[] = [
  { id: "ask", ko: "질의", en: "Ask", badge: "/ask", href: "/ask", adminOnly: false },
  { id: "docs", ko: "문서 · 권한", en: "Documents", badge: "", href: "/documents", adminOnly: false },
  { id: "principals", ko: "계정", en: "Principals", badge: "", href: "/principals", adminOnly: false },
  { id: "logs", ko: "감사 로그", en: "Audit log", badge: "W4", href: "/logs", adminOnly: false },
  // 관리자 전용 — role !== "admin" 이면 배열 자체에 들어가지 않는다(숨김이 아니라 미포함).
  { id: "admin", ko: "관리자 대시보드", en: "Admin", badge: "ADMIN", href: "/admin", adminOnly: true },
];
