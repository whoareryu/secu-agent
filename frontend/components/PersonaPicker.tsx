"use client";

export const PERSONAS = [
  { name: "김개발", label: "김개발 · 개발팀 · 등급 1" },
  { name: "박인사", label: "박인사 · 인사팀 · 등급 2" },
  { name: "최임원", label: "최임원 · 경영지원팀 · 등급 3" },
];

export default function PersonaPicker({
  value,
  onChange,
}: {
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <fieldset style={{ border: "1px solid #ddd", padding: 12, marginTop: 12 }}>
      <legend>페르소나</legend>
      {PERSONAS.map((p) => (
        <label key={p.name} style={{ display: "block", marginBottom: 4 }}>
          <input
            type="radio"
            name="persona"
            value={p.name}
            checked={value === p.name}
            onChange={() => onChange(p.name)}
          />{" "}
          {p.label}
        </label>
      ))}
      <p style={{ fontSize: 13, color: "#555", marginTop: 8, marginBottom: 0 }}>
        인증은 실제 구글 OAuth 입니다. 부서·등급은 시연을 위해 고르는 값이고,
        고른 값이 실제 권한 필터를 그대로 탑니다. 문서와 계정은 합성이며
        ISMS-P 안내서만 실제 공개 표준입니다.
      </p>
    </fieldset>
  );
}
