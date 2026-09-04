import { test } from "node:test";
import assert from "node:assert/strict";
import { citedClauses } from "./cited.ts";

// 검색된 조항 목록을 대신한다. 맨몸 코드는 이 목록에 있을 때만 인용으로
// 본다 — 그래야 날짜 같은 것이 조항으로 오인되지 않는다.
const 검색됨 = ["5.1.1", "2.6.2", "2.6.7"];

test("대괄호로 감싼 코드를 인용으로 본다", () => {
  const r = citedClauses("운영 서버 접속은 [5.1.1] 에 따릅니다.", 검색됨);
  assert.deepEqual(r.cited, ["5.1.1"]);
  assert.deepEqual(r.fabricated, []);
});

test("굵게 표시된 것도 잡는다", () => {
  // 실제 답변이 **[6.1.1]** 형태로 나온다(2026-09-04 관측).
  const r = citedClauses("기준은 **[5.1.1]** 및 **[2.6.2]** 입니다.", 검색됨);
  assert.deepEqual(r.cited, ["5.1.1", "2.6.2"]);
});

test("맨몸 코드는 검색된 것일 때만 인용이다", () => {
  // 프롬프트가 대괄호를 지시하지만 모델은 잊는다. 검색 결과에 있는
  // 코드라면 대괄호가 없어도 인용으로 보는 것이 맞다.
  const r = citedClauses("2.6.2 기준에 따라 통제됩니다.", 검색됨);
  assert.deepEqual(r.cited, ["2.6.2"]);
});

test("날짜를 조항으로 오인하지 않는다", () => {
  // **이 테스트가 맨몸 규칙이 존재하는 이유다.** \d+\.\d+\.\d+ 는 날짜와
  // 구별되지 않는다. 검색 결과에 없는 맨몸 숫자는 무시한다.
  const r = citedClauses("2026.09.04 에 개정되었으며 버전 1.2.3 입니다.", 검색됨);
  assert.deepEqual(r.cited, []);
  assert.deepEqual(r.fabricated, []);
});

test("대괄호인데 검색되지 않은 코드는 지어낸 인용이다", () => {
  // 모델이 없는 조항을 만들어 낸 경우. 답변의 그 부분은 근거가 없다.
  const r = citedClauses("[9.9.9] 에 따라 금지됩니다.", 검색됨);
  assert.deepEqual(r.cited, []);
  assert.deepEqual(r.fabricated, ["9.9.9"]);
});

test("같은 코드를 여러 번 인용해도 한 번만 센다", () => {
  const r = citedClauses("[5.1.1] 과 [5.1.1] 그리고 5.1.1", 검색됨);
  assert.deepEqual(r.cited, ["5.1.1"]);
});

test("등장 순서를 지킨다", () => {
  // 화면이 이 순서로 그린다 — 답변을 읽어 내려가는 순서와 맞아야 한다.
  const r = citedClauses("[2.6.2] 먼저, 그다음 [5.1.1]", 검색됨);
  assert.deepEqual(r.cited, ["2.6.2", "5.1.1"]);
});

test("빈 답변은 아무것도 인용하지 않는다", () => {
  assert.deepEqual(citedClauses("", 검색됨), { cited: [], fabricated: [] });
});

test("검색 결과가 비어도 터지지 않는다", () => {
  // 도구를 안 부르고 바로 답한 경우. 대괄호 인용은 전부 지어낸 것이다.
  const r = citedClauses("[5.1.1] 을 보세요", []);
  assert.deepEqual(r.cited, []);
  assert.deepEqual(r.fabricated, ["5.1.1"]);
});

test("두 자리 이상 절도 잡는다", () => {
  // ISMS-P 는 2.10.1 · 2.12.2 같은 조항이 있다. \d 하나로 쓰면 통째로
  // 놓친다 — 백엔드 파서가 같은 이유로 \d+ 를 쓴다.
  const r = citedClauses("[2.10.1] 과 [2.12.2]", ["2.10.1", "2.12.2"]);
  assert.deepEqual(r.cited, ["2.10.1", "2.12.2"]);
});

test("맨몸과 대괄호가 섞여도 답변 순서를 지킨다", () => {
  // 대괄호를 먼저 훑고 맨몸을 나중에 훑던 첫 판은 여기서 순서가 뒤집혔다.
  // 화면이 이 순서로 그리므로 답변을 읽어 내려가는 순서와 맞아야 한다.
  const r = citedClauses("먼저 2.6.2 를 보고, 그다음 [5.1.1] 을 본다", 검색됨);
  assert.deepEqual(r.cited, ["2.6.2", "5.1.1"]);
});
