import { test } from "node:test";
import assert from "node:assert/strict";
import { roleFor } from "./session.ts";

// roleFor 는 /admin 화면과 /api/access-log 를 막는 유일한 판단이다. 요금
// 상한은 테스트 5개와 뮤테이션 검사를 받았는데 인가 경계는 둘 다 못 받았다.
// 순서가 거꾸로였다.

test("알리스트 안의 이메일은 admin", () => {
  process.env.ADMIN_EMAILS = "boss@x.com,admin@x.com";
  assert.equal(roleFor("boss@x.com"), "admin");
  assert.equal(roleFor("admin@x.com"), "admin");
});

test("알리스트 밖의 이메일은 member", () => {
  process.env.ADMIN_EMAILS = "boss@x.com";
  assert.equal(roleFor("someone@x.com"), "member");
});

test("알리스트가 비어 있으면 아무도 admin 이 아니다", () => {
  // 여기가 뒤집히면 로그인한 누구나 감사 로그를 읽는다. 설정 누락이
  // "모두 관리자" 가 되는 것이 이 게이트의 최악 실패다.
  process.env.ADMIN_EMAILS = "";
  for (const email of ["boss@x.com", "anyone@x.com", "a@b.c"]) {
    assert.equal(roleFor(email), "member", `빈 알리스트에서 ${email} 이 admin 이 됐다`);
  }
});

test("ADMIN_EMAILS 가 아예 없어도 아무도 admin 이 아니다", () => {
  delete process.env.ADMIN_EMAILS;
  assert.equal(roleFor("boss@x.com"), "member");
});

test("빈 이메일은 member — 알리스트에 빈 항목이 있어도 마찬가지다", () => {
  // 쉼표만 늘어놓은 값은 빈 문자열 항목을 만든다. 그것이 걸러지지 않으면
  // 이메일 없는 세션이 admin 으로 통과한다.
  process.env.ADMIN_EMAILS = ",, ,";
  for (const email of [null, undefined, ""]) {
    assert.equal(roleFor(email), "member", `${JSON.stringify(email)} 이 admin 이 됐다`);
  }
});

test("알리스트 항목의 공백은 잘린다", () => {
  process.env.ADMIN_EMAILS = " boss@x.com , admin@x.com ";
  assert.equal(roleFor("boss@x.com"), "admin");
  assert.equal(roleFor("admin@x.com"), "admin");
  // 공백을 남긴 채로 비교하면 안 된다 — 그러면 진짜 이메일이 막힌다.
  assert.equal(roleFor(" boss@x.com "), "member");
});
