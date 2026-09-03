// LLM 답변의 마크다운을 구조로 바꾼다.
//
// 왜 필요한가: 답변을 whiteSpace: pre-wrap 으로 그대로 뿌리고 있었고,
// Gemini 는 마크다운으로 답한다 — 화면에 `* **[4.2.2] ...**:` 가 기호째
// 보였다. 제품에서 가장 자주 보는 화면의 가장 큰 흠이었다.
//
// **HTML 을 만들지 않는다.** 이 파일은 문자열을 자료구조로만 바꾸고,
// 렌더는 호출부가 React 엘리먼트로 한다 — dangerouslySetInnerHTML 을 쓰면
// LLM 이 낸 문자열이 곧 마크업이 되어, 근거 없는 내용을 화면에 못 두게
// 막아온 규율이 주입 경로로 바뀐다.
//
// 라이브러리를 넣지 않은 이유: 필요한 것은 굵게·목록·제목 넷뿐이고,
// 마크다운 전체를 지원하면 지원한 만큼 표면이 는다.

export type Span = { t: "text" | "b" | "code"; v: string };

export type Block =
  | { kind: "h"; spans: Span[] }
  | { kind: "p"; spans: Span[] }
  | { kind: "ul"; items: Span[][] }
  | { kind: "ol"; items: Span[][] }
  | { kind: "hr" };

/** `**굵게**` 와 `` `코드` `` 를 스팬으로 가른다. 짝이 안 맞으면 글자 그대로 둔다. */
export function parseInline(line: string): Span[] {
  const spans: Span[] = [];
  let buf = "";
  let i = 0;
  const flush = () => {
    if (buf) spans.push({ t: "text", v: buf });
    buf = "";
  };
  while (i < line.length) {
    if (line.startsWith("**", i)) {
      const end = line.indexOf("**", i + 2);
      if (end > i + 2) {
        flush();
        spans.push({ t: "b", v: line.slice(i + 2, end) });
        i = end + 2;
        continue;
      }
    }
    if (line[i] === "`") {
      const end = line.indexOf("`", i + 1);
      if (end > i + 1) {
        flush();
        spans.push({ t: "code", v: line.slice(i + 1, end) });
        i = end + 1;
        continue;
      }
    }
    buf += line[i];
    i += 1;
  }
  flush();
  return spans;
}

const 글머리 = /^\s*[-*]\s+/;
const 번호 = /^\s*\d+\.\s+/;
const 제목 = /^\s*#{1,6}\s+/;
const 가로줄 = /^\s*(-{3,}|\*{3,}|_{3,})\s*$/;

/** 줄 단위로 블록을 만든다. 같은 종류의 목록 줄은 한 블록으로 모은다. */
export function parseBlocks(text: string): Block[] {
  const blocks: Block[] = [];
  const lines = (text ?? "").split("\n");
  let 문단: string[] = [];

  const 문단닫기 = () => {
    if (!문단.length) return;
    blocks.push({ kind: "p", spans: parseInline(문단.join(" ")) });
    문단 = [];
  };

  for (const raw of lines) {
    const line = raw.replace(/\s+$/, "");
    if (!line.trim()) {
      문단닫기();
      continue;
    }
    if (가로줄.test(line)) {
      문단닫기();
      blocks.push({ kind: "hr" });
      continue;
    }
    if (제목.test(line)) {
      문단닫기();
      blocks.push({ kind: "h", spans: parseInline(line.replace(제목, "")) });
      continue;
    }
    if (글머리.test(line) || 번호.test(line)) {
      문단닫기();
      const ordered = 번호.test(line);
      const kind = ordered ? "ol" : "ul";
      const item = parseInline(line.replace(ordered ? 번호 : 글머리, ""));
      const last = blocks[blocks.length - 1];
      if (last && last.kind === kind) last.items.push(item);
      else blocks.push({ kind, items: [item] } as Block);
      continue;
    }
    문단.push(line.trim());
  }
  문단닫기();
  return blocks;
}
