import { test } from "node:test";
import assert from "node:assert/strict";
import { check } from "./rate-limit.ts";

test("알리스트 안은 무제한", () => {
  process.env.ASK_ALLOWLIST = "unlimited@x.com";
  process.env.ASK_DAILY_LIMIT = "1";
  for (let i = 0; i < 5; i++) {
    const r = check("unlimited@x.com");
    assert.equal(r.allowed, true);
    assert.equal(r.remaining, null);
  }
});

test("알리스트 밖은 DAILY_LIMIT 회까지 통과하고 그 다음 차단된다", () => {
  process.env.ASK_ALLOWLIST = "";
  process.env.ASK_DAILY_LIMIT = "3";
  const email = "limited-a@x.com";
  assert.equal(check(email).allowed, true);
  assert.equal(check(email).allowed, true);
  const third = check(email);
  assert.equal(third.allowed, true);
  assert.equal(third.remaining, 0);
  const fourth = check(email);
  assert.equal(fourth.allowed, false);
  assert.equal(fourth.remaining, 0);
});

test("날짜가 바뀌면(UTC 기준) 리셋된다", () => {
  process.env.ASK_ALLOWLIST = "";
  process.env.ASK_DAILY_LIMIT = "1";
  const email = "date-reset@x.com";
  const day1 = new Date("2026-08-31T23:59:00Z");
  const day1Later = new Date("2026-08-31T23:59:30Z");
  const day2 = new Date("2026-09-01T00:00:00Z");
  assert.equal(check(email, day1).allowed, true);
  assert.equal(check(email, day1Later).allowed, false); // 같은 UTC 날짜, 여전히 상한
  assert.equal(check(email, day2).allowed, true); // 다음 UTC 날짜, 리셋
});

test("이메일이 다르면 카운터가 섞이지 않는다", () => {
  process.env.ASK_ALLOWLIST = "";
  process.env.ASK_DAILY_LIMIT = "1";
  assert.equal(check("mix-a@x.com").allowed, true);
  assert.equal(check("mix-b@x.com").allowed, true); // 별개 카운터라 b 는 영향받지 않는다
  assert.equal(check("mix-a@x.com").allowed, false); // a 는 이미 소진
});

test("알리스트가 비어 있어도 밖의 사용자가 무제한이 되지 않는다", () => {
  process.env.ASK_ALLOWLIST = "";
  process.env.ASK_DAILY_LIMIT = "2";
  const email = "fail-closed@x.com";
  const results = [check(email), check(email), check(email)];
  assert.equal(results.filter((r) => r.allowed).length, 2);
  assert.equal(results[2].allowed, false);
});
