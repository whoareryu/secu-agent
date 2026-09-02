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

// POST /demo/compare 응답. backend/api/schemas.py 의 DemoPathResult ·
// DemoPersonaView · CompareResponse 를 그대로 미러링한다.
export type DemoPathResult = {
  count: number;
  clause_codes: string[];
};

export type DemoPersonaView = {
  name: string;
  department: string;
  clearance: number;
  prefiltered: DemoPathResult;
  naive: DemoPathResult;
};

export type CompareResponse = {
  query: string;
  k: number;
  personas: DemoPersonaView[];
};

// 앱 셸의 사이드바 메뉴 · 헤더 제목이 함께 참조하는 화면 메타데이터.
export type NavItem = {
  id: string;
  ko: string;
  en: string;
  badge: string;
  href: string;
  adminOnly: boolean;
};
