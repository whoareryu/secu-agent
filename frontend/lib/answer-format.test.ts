import { test } from "node:test";
import assert from "node:assert/strict";
import { parseBlocks, parseInline } from "./answer-format.ts";

test("굵게와 코드를 스팬으로 가른다", () => {
  assert.deepEqual(parseInline("비밀번호는 **90일마다 변경**해야"), [
    { t: "text", v: "비밀번호는 " },
    { t: "b", v: "90일마다 변경" },
    { t: "text", v: "해야" },
  ]);
  assert.deepEqual(parseInline("`visible()` 하나"), [
    { t: "code", v: "visible()" },
    { t: "text", v: " 하나" },
  ]);
});

test("짝이 맞지 않는 기호는 글자 그대로 둔다", () => {
  // LLM 출력은 항상 온전한 마크다운이 아니다. 반쪽짜리 기호를 만나면
  // 조용히 지우는 대신 보이는 대로 둔다 — 지우면 답변이 바뀐다.
  assert.deepEqual(parseInline("2 ** 3 은"), [{ t: "text", v: "2 ** 3 은" }]);
  assert.deepEqual(parseInline("남은 ` 하나"), [{ t: "text", v: "남은 ` 하나" }]);
});

test("연속된 글머리는 한 목록으로 모인다", () => {
  const b = parseBlocks("* 첫째\n* 둘째\n\n뒷문장");
  assert.equal(b.length, 2);
  assert.equal(b[0].kind, "ul");
  assert.equal(b[0].kind === "ul" ? b[0].items.length : 0, 2);
  assert.equal(b[1].kind, "p");
});

test("번호 목록과 글머리 목록은 섞이지 않는다", () => {
  const b = parseBlocks("1. 하나\n2. 둘\n- 셋");
  assert.deepEqual(b.map((x) => x.kind), ["ol", "ul"]);
});

test("제목과 가로줄을 알아본다", () => {
  const b = parseBlocks("### 사내 접수\n---\n본문");
  assert.deepEqual(b.map((x) => x.kind), ["h", "hr", "p"]);
  assert.deepEqual(b[0].kind === "h" ? b[0].spans : [], [{ t: "text", v: "사내 접수" }]);
});

test("빈 줄로 갈린 문단은 따로, 이어진 줄은 한 문단으로", () => {
  const b = parseBlocks("한 줄\n이어진 줄\n\n다음 문단");
  assert.equal(b.length, 2);
  assert.deepEqual(b[0].kind === "p" ? b[0].spans : [], [{ t: "text", v: "한 줄 이어진 줄" }]);
});

test("빈 답변은 블록이 없다", () => {
  assert.deepEqual(parseBlocks(""), []);
  assert.deepEqual(parseBlocks("\n\n  \n"), []);
});
