import { test } from "node:test";
import assert from "node:assert/strict";
import { personaFrom } from "./persona.ts";

// 쿠키는 브라우저가 보내는 값이라 믿지 않는다. 여기서 걸러지지 않으면
// 알 수 없는 이름이 그대로 백엔드로 가고, 백엔드는 "알 수 없는 페르소나"
// 400 을 내며 화면은 원인을 말하지 못한 채 깨진다.

const 세명 = ["김개발", "박인사", "최임원"];

test("알려진 이름은 그대로 통과한다", () => {
  assert.equal(personaFrom("김개발", 세명), "김개발");
  assert.equal(personaFrom("최임원", 세명), "최임원");
});

test("알려지지 않은 이름은 null", () => {
  assert.equal(personaFrom("없는사람", 세명), null);
});

test("쿠키가 없으면 null", () => {
  assert.equal(personaFrom(undefined, 세명), null);
  assert.equal(personaFrom("", 세명), null);
});

test("목록이 비어 있으면 무엇도 통과하지 않는다", () => {
  // 백엔드가 죽어 principals 를 못 불러왔을 때 이 함수가 열리는 쪽으로
  // 틀리면, 아무 이름이나 담긴 쿠키로 직원 면에 들어간다.
  assert.equal(personaFrom("김개발", []), null);
});

test("앞뒤 공백이 붙은 값은 통과하지 않는다", () => {
  // 공백을 잘라 받아주면 " 김개발 " 과 "김개발" 이 다른 쿠키인데 같은
  // 사람이 되어, 나중에 쿠키를 키로 쓰는 코드가 조용히 갈린다.
  assert.equal(personaFrom(" 김개발", 세명), null);
});
