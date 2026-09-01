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
    <div className="seg" style={{ display: "flex" }}>
      {personas.map((p) => (
        <label
          key={p.name}
          className="seg-opt"
          style={{ flex: 1, flexDirection: "column", alignItems: "flex-start", gap: 2, padding: "10px 14px" }}
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
