// 한글 조사 — 앞말의 받침에 따라 갈린다.
//
// 페르소나 이름을 화면에 박아두지 않게 된 뒤로(계정이 10개다) 조사를
// 손으로 고를 수 없다. 실제로 그렇게 깨졌다: logs 화면이 `{주체}이` 로
// 하드코딩돼 있어 김개발·이보안에는 맞았지만 서인사·박인사·윤총무·남감사
// 에서 "서인사이 볼 수 있는" 이 됐다.
//
// 한글 음절은 유니코드에서 (초성, 중성, 종성) 이 규칙적으로 합성돼 있어
// 종성 유무를 산술로 판정할 수 있다. AC00 이 '가', 종성은 28가지(없음
// 포함)라 28로 나눈 나머지가 0이면 받침이 없다.
function 받침(word: string): boolean | null {
  const last = word.trim().at(-1);
  if (!last) return null;
  const code = last.charCodeAt(0);
  if (code < 0xac00 || code > 0xd7a3) return null; // 한글 음절이 아니면 모른다
  return (code - 0xac00) % 28 !== 0;
}

/** 이 / 가 — 받침이 있으면 "이". 한글이 아니면 "이(가)" 로 둘 다 적는다. */
export function 이가(word: string): string {
  const b = 받침(word);
  return b === null ? "이(가)" : b ? "이" : "가";
}

/** 으로 / 로 — 받침이 없거나 ㄹ 받침이면 "로". */
export function 으로(word: string): string {
  const b = 받침(word);
  if (b === null) return "(으)로";
  if (!b) return "로";
  const 종성 = (word.trim().charCodeAt(word.trim().length - 1) - 0xac00) % 28;
  return 종성 === 8 ? "로" : "으로"; // 8 = ㄹ
}
