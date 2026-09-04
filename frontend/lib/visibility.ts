import type { Principal } from "../components/PersonaSegment.tsx";

// GET /documents 가 돌려주는 형태 그대로 — 권한 필터 없이 전부.
export type Document = {
  id: number;
  title: string;
  doc_type: string;
  required_clearance: number;
  allowed_departments: string[];
  source_path: string;
  chunk_count: number;
};

// backend/core/access/visibility.py 의 규칙과 같아야 한다 — SQL(chunk_search.
// _권한_WHERE) · 파이썬(visibility.py)에 이은 세 번째 사본. 허용 부서가
// 비어 있으면 전사 공개다("아무도 못 본다"가 아니다).
//
// `lib/` 에 있는 이유가 둘이다. 서버 컴포넌트가 불러야 하고(클라이언트
// 모듈에 두면 못 부른다), 세 번째 사본인데 여기 오기 전까지 테스트가
// 하나도 없었다 — npm test 는 lib/ 만 본다.
//
// `p` 가 없을 수 있다. 타입은 Principal 을 요구하지만 (explain)/documents 의
// `personas.find(...) ?? personas[0]` 은 목록이 비면 undefined 를 흘린다 —
// 실측: TypeError: Cannot read properties of undefined (reading 'clearance').
// 앱에 error.tsx 가 없어 그 예외가 화면 전체를 Next 기본 오류로 바꿨다.
// 여기서는 **닫히는 쪽**으로 답한다 — 주체를 모르면 보이지 않는다.
export function visible(d: Document, p: Principal | undefined): boolean {
  if (!p) return false;
  return (
    d.required_clearance <= p.clearance &&
    (d.allowed_departments.length === 0 || d.allowed_departments.includes(p.department))
  );
}
