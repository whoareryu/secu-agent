import { test } from "node:test";
import assert from "node:assert/strict";
import { guard, navFor } from "./surface.ts";

// 면 접근 판정은 컴포넌트 안에 두지 않는다. 지금 프론트엔드에는 컴포넌트를
// 도는 자동 검증이 하나도 없어서(npm test 는 lib/ 만 본다), 컴포넌트 안에
// 넣는 순간 이 판정은 아무도 검사하지 않는 코드가 된다.

test("직원 면은 페르소나가 없으면 허브로 보낸다", () => {
  assert.equal(guard({ surface: "employee", hasPersona: false, role: "member" }), "to-hub");
});

test("직원 면은 페르소나가 있으면 통과한다", () => {
  assert.equal(guard({ surface: "employee", hasPersona: true, role: "member" }), "ok");
});

test("관리자 면은 member 를 허브로 보낸다", () => {
  // 사이드바에서 메뉴를 빼는 것은 프레젠테이션일 뿐이다 — 주소창에 직접
  // 입력할 수 있으므로 이 판정이 진짜 문이다.
  assert.equal(guard({ surface: "admin", hasPersona: false, role: "member" }), "to-hub");
  assert.equal(guard({ surface: "admin", hasPersona: true, role: "member" }), "to-hub");
});

test("관리자 면은 admin 을 페르소나 없이도 통과시킨다", () => {
  // 관리자 면은 한 사람이 되어보는 곳이 아니라 장치를 들여다보는 곳이다.
  assert.equal(guard({ surface: "admin", hasPersona: false, role: "admin" }), "ok");
});

test("설명 면은 로그인만 되어 있으면 통과한다", () => {
  assert.equal(guard({ surface: "explain", hasPersona: false, role: "member" }), "ok");
});

test("직원 면 네비에 설명·관리자 항목이 없다", () => {
  // 직원 화면에 "직원이 볼 리 없는 메뉴" 가 섞이면 그 화면은 다시
  // 조작판으로 읽힌다.
  const ids = navFor("employee").map((i) => i.id);
  assert.deepEqual(ids, ["ask", "my-docs"]);
});

test("관리자 면 네비에 감사 로그가 있다", () => {
  assert.deepEqual(navFor("admin").map((i) => i.id), ["logs", "admin"]);
});
