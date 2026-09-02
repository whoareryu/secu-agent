// 페르소나 이름을 담는 쿠키. **이름만 담는다** — 등급·부서를 담으면
// 클라이언트가 자기 권한을 정하게 되고, 그것이 api/schemas.py 가 막아둔
// 사칭 경로다. 이름은 백엔드가 principals 테이블에서 등급으로 번역한다.
export const PERSONA_COOKIE = "secuagent_persona";

// 쿠키값이 실제로 존재하는 페르소나인지 판정한다. 목록은 호출부가
// 백엔드에서 받아 넘긴다 — 이름을 여기에 하드코딩하면 계정이 늘었을 때
// 화면이 따라오지 못한다.
export function personaFrom(raw: string | undefined, known: string[]): string | null {
  if (!raw) return null;
  return known.includes(raw) ? raw : null;
}
