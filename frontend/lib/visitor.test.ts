import { test } from "node:test";
import assert from "node:assert/strict";
import { VISITOR_COOKIE, newVisitorId } from "./visitor.ts";

test("쿠키 이름이 고정돼 있다", () => {
  // 이름이 갈리면 심는 쪽과 읽는 쪽이 조용히 어긋나고, 그러면 모든 방문자가
  // 자기 질의를 못 알아본다 — 화면은 멀쩡해 보인다.
  assert.equal(VISITOR_COOKIE, "sa_vid");
});

test("매번 다른 값이 나온다", () => {
  const 값 = new Set(Array.from({ length: 200 }, () => newVisitorId()));
  assert.equal(값.size, 200);
});

test("추측할 수 없을 만큼 길다", () => {
  // 남의 세션 id 를 맞히면 그 사람의 질의 원문이 보인다. 인증은 아니지만
  // 우연히 맞는 일은 없어야 한다.
  assert.ok(newVisitorId().length >= 32, newVisitorId());
});
