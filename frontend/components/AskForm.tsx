"use client";

import { useState } from "react";
import Answer, { type AskResult } from "./Answer";
import PersonaPicker from "./PersonaPicker";

export default function AskForm() {
  const [query, setQuery] = useState("");
  const [persona, setPersona] = useState("김개발");
  const [result, setResult] = useState<AskResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const r = await fetch("/api/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, persona }),
      });
      if (!r.ok) throw new Error(`요청이 실패했습니다 (${r.status})`);
      setResult(await r.json());
    } catch (err) {
      setError(err instanceof Error ? err.message : "알 수 없는 오류");
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <form onSubmit={submit}>
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="예: 비밀번호는 얼마나 자주 바꿔야 하나"
          required
          maxLength={500}
          style={{ width: "100%", padding: 8, fontSize: 16 }}
        />
        <PersonaPicker value={persona} onChange={setPersona} />
        <button type="submit" disabled={loading} style={{ marginTop: 12, padding: "8px 16px" }}>
          {loading ? "찾는 중…" : "묻기"}
        </button>
      </form>
      {loading && (
        <p style={{ color: "#666", fontSize: 14 }}>
          처음 요청은 백엔드가 잠들어 있었다면 모델을 올리느라 수십 초 걸릴 수 있습니다.
        </p>
      )}
      {error && <p style={{ color: "#b00" }}>{error}</p>}
      {result && <Answer result={result} />}
    </>
  );
}
