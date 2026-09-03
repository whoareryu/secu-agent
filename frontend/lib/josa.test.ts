import { test } from "node:test";
import assert from "node:assert/strict";
import { 이가, 으로 } from "./josa.ts";

// data/principals.json 의 열 이름을 그대로 쓴다 — 이 목록이 늘어나서
// 조사가 깨졌으므로 회귀 테스트도 이 목록으로 건다.
test("이/가는 받침으로 갈린다", () => {
  assert.equal(이가("김개발"), "이"); // ㄹ
  assert.equal(이가("정개발"), "이");
  assert.equal(이가("이보안"), "이"); // ㄴ
  assert.equal(이가("한보안"), "이");
  assert.equal(이가("오보안"), "이");
  assert.equal(이가("최임원"), "이"); // ㄴ
  assert.equal(이가("서인사"), "가"); // 받침 없음
  assert.equal(이가("박인사"), "가");
  assert.equal(이가("윤총무"), "가");
  assert.equal(이가("남감사"), "가");
});

test("으로/로는 ㄹ 받침을 예외로 둔다", () => {
  assert.equal(으로("김개발"), "로"); // ㄹ 받침은 "로"
  assert.equal(으로("최임원"), "으로"); // ㄴ
  assert.equal(으로("한보안"), "으로");
  assert.equal(으로("서인사"), "로"); // 받침 없음
  assert.equal(으로("윤총무"), "로");
});

test("한글이 아니면 단정하지 않는다", () => {
  assert.equal(이가("admin"), "이(가)");
  assert.equal(으로("admin"), "(으)로");
  assert.equal(이가(""), "이(가)");
});
