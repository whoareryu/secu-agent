import { test } from "node:test";
import assert from "node:assert/strict";
import { roleOf } from "./principals.ts";
import type { Principal } from "../components/PersonaSegment.tsx";

// roleOf 가 관리자 면 판정의 **입력**을 만든다. guard() 는 테스트가 있는데
// 그 입력을 구하는 쪽이 없으면, 판정이 맞아도 잘못된 값을 받아 열릴 수 있다.
// 특히 "못 찾으면 member" 라는 닫히는 기본값은 뒤집혀도 조용하다.

const 목록: Principal[] = [
  { name: "가", department: "개발팀", clearance: 1, role: "member" },
  { name: "나", department: "감사팀", clearance: 2, role: "auditor" },
];

test("목록에 있는 이름은 그 계정의 역할을 준다", () => {
  assert.equal(roleOf(목록, "나"), "auditor");
  assert.equal(roleOf(목록, "가"), "member");
});

test("목록에 없는 이름은 member", () => {
  // 낡은 쿠키나 편집된 쿠키가 이 경로로 온다. 여기서 undefined 가 새면
  // guard 는 role !== "auditor" 로 막아주지만, 기본값이 무엇인지는 이 함수가
  // 정한다 — 그 책임을 여기서 고정한다.
  assert.equal(roleOf(목록, "없는이름"), "member");
});

test("이름이 없으면 member", () => {
  assert.equal(roleOf(목록, null), "member");
});

test("빈 목록에서는 누구도 auditor 가 아니다", () => {
  // 백엔드가 빈 배열을 주는 상황(마이그레이션 직후 등)에서 이것이 뒤집히면
  // 관리자 면이 아무에게나 열린다. 설정 누락이 "모두 통과" 가 되는 것이
  // 이 종류 게이트의 최악 실패다.
  assert.equal(roleOf([], "나"), "member");
  assert.equal(roleOf([], null), "member");
});
