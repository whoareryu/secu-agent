// 답변이 실제로 인용한 조항과, 검색만 된 조항을 가른다.
//
// **왜 필요한가.** 화면은 검색 결과 상위 k 를 "근거 조항" 이라고 불렀다.
// 그런데 답변이 실제로 인용하는 것은 보통 한둘이고 나머지는 그냥 질의와
// 가까운 자료다. 더 나쁜 경우도 있었다 — 답변이 "찾지 못했습니다" 인데
// 아래에 "근거 조항" 일곱 개가 붙었다. 근거가 아닌 것을 근거라고 부르면
// 그 자체가 뒷받침 없는 문장이다.
//
// 가르고 나면 하나가 공짜로 따라온다: **답변이 인용했는데 검색 결과에는
// 없는 코드** — 모델이 지어낸 인용이다. README 가 "Faithfulness 는 LLM
// 심판이 아니라 조항 코드의 실재 여부로 잰다" 고 적어둔 그 방식의 1단계다.

// 조항 코드. 각 자리가 `\d+` 인 이유는 백엔드 파서와 같다 — `\d` 하나로
// 쓰면 2.10.1 · 2.12.2 처럼 두 자리 절을 통째로 놓친다.
const 코드 = String.raw`(\d+\.\d+\.\d+)`;
// **한 번에 훑는다.** 대괄호를 먼저 훑고 맨몸을 나중에 훑으면, 답변에서
// 뒤에 나온 대괄호 인용이 앞의 맨몸 인용보다 앞으로 온다 — 화면이 답변을
// 읽어 내려가는 순서와 어긋난다(실측으로 잡았다).
// 대괄호가 있으면 group 1, 없으면 group 2 가 찬다.
const 인용 = new RegExp(String.raw`\[${코드}\]|${코드}`, "g");

export type CitedSplit = {
  /** 답변이 인용했고 검색 결과에도 있는 코드. 등장 순서. */
  cited: string[];
  /** 답변이 인용했지만 검색 결과에 없는 코드 — 지어낸 인용. */
  fabricated: string[];
};

/**
 * 답변 텍스트에서 인용된 조항 코드를 뽑아 검색 결과와 대조한다.
 *
 * 두 규칙을 쓴다:
 *
 * - `[5.1.1]` 대괄호는 **무조건** 인용으로 본다. 검색 결과에 없으면
 *   지어낸 인용이다.
 * - 맨몸 `5.1.1` 은 검색 결과에 있을 때만 인용으로 본다.
 *
 * 맨몸을 제한하는 이유는 `2026.09.04` 같은 날짜가 같은 모양이기 때문이다.
 * 검색 결과로 좁히면 그 오탐이 사라지고, 대신 "대괄호 없이 지어낸 인용"은
 * 놓친다 — 프롬프트가 대괄호를 지시하므로 그쪽이 훨씬 드물다.
 */
export function citedClauses(answer: string, hitCodes: string[]): CitedSplit {
  const 검색됨 = new Set(hitCodes);
  const cited: string[] = [];
  const fabricated: string[] = [];
  const 본_것 = new Set<string>();

  const 담는다 = (code: string, 대괄호: boolean) => {
    if (본_것.has(code)) return;
    if (검색됨.has(code)) {
      본_것.add(code);
      cited.push(code);
    } else if (대괄호) {
      본_것.add(code);
      fabricated.push(code);
    }
    // 대괄호 없고 검색 결과에도 없으면 조항이 아니다(날짜·버전 등).
  };

  for (const m of answer.matchAll(인용)) {
    const 대괄호 = m[1] !== undefined;
    담는다(대괄호 ? m[1] : m[2], 대괄호);
  }

  return { cited, fabricated };
}
