import { test } from "node:test";
import assert from "node:assert/strict";
import { visible, type Document } from "./visibility.ts";

// 권한 규칙의 세 번째 사본이다 — SQL 과 파이썬에 이은. 앞의 둘은
// test_permission_sql.py 와 test_visibility.py 가 지키는데 이것만
// 무방비였다. 어긋나면 화면이 조용히 틀린 목록을 보여준다.

const 문서 = (등급: number, 부서: string[]): Document => ({
  id: 1, title: "t", doc_type: "md", required_clearance: 등급,
  allowed_departments: 부서, source_path: "p", chunk_count: 1,
});
const 사원 = { name: "김개발", department: "개발팀", clearance: 1 };
const 임원 = { name: "최임원", department: "경영지원팀", clearance: 3 };

test("등급이 모자라면 안 보인다", () => {
  assert.equal(visible(문서(3, []), 사원), false);
});

test("등급이 충분하면 보인다", () => {
  assert.equal(visible(문서(1, []), 사원), true);
  assert.equal(visible(문서(3, []), 임원), true);
});

test("허용 부서가 비면 전사 공개다", () => {
  // 여기가 뒤집히면 전사 공개 문서가 아무에게도 안 보인다 — 에러가
  // 아니라 조용한 누락이라 발견이 늦다(W1 실측).
  assert.equal(visible(문서(1, []), 사원), true);
  assert.equal(visible(문서(1, []), 임원), true);
});

test("부서가 다르면 등급이 높아도 안 보인다", () => {
  // 권한은 사다리가 아니라 격자다 — verification.markdown 항목 ⑧.
  assert.equal(visible(문서(1, ["개발팀"]), 임원), false);
  assert.equal(visible(문서(1, ["개발팀"]), 사원), true);
});

test("주체를 모르면 보이지 않는다", () => {
  // (explain)/documents 는 personas 가 비면 personas[0] 으로 undefined 를
  // 흘린다. 던지면 error.tsx 가 없어 화면 전체가 죽고, true 를 돌려주면
  // 권한 없는 문서가 보인다 — 닫히는 쪽으로 답한다.
  assert.equal(visible(문서(1, []), undefined), false);
});
