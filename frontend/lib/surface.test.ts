import { test } from "node:test";
import assert from "node:assert/strict";
import { guard, navFor } from "./surface.ts";

// 면 접근 판정은 컴포넌트 안에 두지 않는다. 지금 프론트엔드에는 컴포넌트를
// 도는 자동 검증이 하나도 없어서(npm test 는 lib/ 만 본다), 컴포넌트 안에
// 넣는 순간 이 판정은 아무도 검사하지 않는 코드가 된다.

test("관리자 면은 감사 역할만 통과한다", () => {
  assert.equal(guard({ surface: "admin", hasPersona: true, role: "auditor" }), "ok");
  assert.equal(guard({ surface: "admin", hasPersona: true, role: "member" }), "to-hub");
  assert.equal(guard({ surface: "admin", hasPersona: true, role: "developer" }), "to-hub");
});

test("관리자 면은 페르소나가 없으면 허브로 보낸다", () => {
  // 역할은 페르소나에서 온다. 페르소나가 없으면 역할도 없다.
  assert.equal(guard({ surface: "admin", hasPersona: false, role: "member" }), "to-hub");
  // 역할이 auditor 인데도 페르소나가 없으면 막혀야 한다. 이 줄이 없으면 위
  // 한 줄은 role !== "auditor" 만으로도 통과해서, 페르소나 없는 경로를 닫는
  // 절(!hasPersona)에 덮개가 하나도 없게 된다 — 지우고 돌려도 여섯 개가 다
  // 초록이었다. 통과하지만 이유가 틀린 단언은 덮개가 아니다.
  assert.equal(guard({ surface: "admin", hasPersona: false, role: "auditor" }), "to-hub");
});

test("설명 면은 로그인도 페르소나도 요구하지 않는다", () => {
  assert.equal(guard({ surface: "explain", hasPersona: false, role: "member" }), "ok");
});

test("직원 면은 페르소나만 요구한다", () => {
  assert.equal(guard({ surface: "employee", hasPersona: true, role: "member" }), "ok");
  assert.equal(guard({ surface: "employee", hasPersona: false, role: "member" }), "to-hub");
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
