"use client";

import Blueprint from "./Blueprint";

const SAMPLES = [
  "임원 성과급은 어떤 기준으로 정해지나",
  "운영 서버에 접속하려면 어떤 승인이 필요한가",
  "비밀번호는 얼마나 자주 바꿔야 하나",
];

export default function RightRail({
  query,
  onSelectSample,
}: {
  query: string;
  onSelectSample: (text: string) => void;
}) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <Blueprint className="card" style={{ padding: 18, gap: 10 }}>
        <div className="card-kicker">예시 질의</div>
        {SAMPLES.map((s) => (
          <button
            key={s}
            type="button"
            className="btn btn-secondary"
            style={{
              justifyContent: "flex-start",
              textAlign: "left",
              fontSize: 12.5,
              height: "auto",
              padding: "9px 11px",
              whiteSpace: "normal",
            }}
            onClick={() => onSelectSample(s)}
          >
            {s}
          </button>
        ))}
        <p style={{ margin: 0, fontSize: 11.5, color: "var(--color-neutral-600)" }}>
          같은 질문을 김개발·박인사·최임원 세 계정으로 비교하는 것은{" "}
          <a href="/how">동작 원리</a> 화면에서 볼 수 있습니다 — 그쪽은 LLM 을 부르지
          않아 질의 횟수를 쓰지 않습니다.
        </p>
      </Blueprint>
    </div>
  );
}
