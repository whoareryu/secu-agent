"use client";

// GET /api/principals 가 돌려주는 형태 그대로. 이름을 하드코딩하지 않는
// 이유는 백엔드가 principals 테이블을 읽기 때문 — 계정을 늘리면 화면이
// 따라온다.
export type Principal = { name: string; department: string; clearance: number };

export default function PersonaSegment({
  personas,
  value,
  onChange,
}: {
  personas: Principal[];
  value: string;
  onChange: (name: string) => void;
}) {
  return (
    // flex 로 두면 마지막 줄의 항목만 남은 폭을 나눠 가져 칸 너비가 줄마다
    // 달라진다(계정 10개 = 7 + 3). 격자로 두면 몇 줄이 되든 칸이 같다.
    <div
      className="seg"
      style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(152px, 1fr))" }}
    >
      {personas.map((p) => (
        <label
          key={p.name}
          className="seg-opt"
          style={{ flexDirection: "column", alignItems: "flex-start", gap: 2, padding: "10px 14px" }}
        >
          <input
            type="radio"
            name="persona"
            value={p.name}
            checked={value === p.name}
            onChange={() => onChange(p.name)}
          />
          <span style={{ fontSize: 15, fontFamily: "var(--font-heading)", letterSpacing: ".02em" }}>{p.name}</span>
          <span style={{ fontSize: 11.5, opacity: 0.75 }}>
            {p.department} · 등급 {p.clearance}
          </span>
        </label>
      ))}
    </div>
  );
}
