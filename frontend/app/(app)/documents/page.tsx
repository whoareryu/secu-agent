"use client";

import { useEffect, useState } from "react";
import DocumentTable, { type Document } from "@/components/DocumentTable";
import type { Principal } from "@/components/PersonaSegment";

// 페르소나 3명은 하드코딩하지 않는다 — GET /api/principals 를 그대로 쓴다.
// 문서는 GET /api/documents 가 권한 필터 없이 전부 돌려준다: 이 화면은
// "규칙이 어떻게 적용되는지"를 보여주는 자리이므로 가시성을 페르소나별로
// 클라이언트가 계산한다(DocumentTable.tsx 의 visible()).
export default function DocumentsPage() {
  const [personas, setPersonas] = useState<Principal[] | null>(null);
  const [documents, setDocuments] = useState<Document[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [personaName, setPersonaName] = useState("");

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      fetch("/api/principals").then((r) => {
        if (!r.ok) throw new Error(`principals ${r.status}`);
        return r.json() as Promise<Principal[]>;
      }),
      fetch("/api/documents").then((r) => {
        if (!r.ok) throw new Error(`documents ${r.status}`);
        return r.json() as Promise<Document[]>;
      }),
    ])
      .then(([p, d]) => {
        if (cancelled) return;
        setPersonas(p);
        setPersonaName((prev) => prev || p[0]?.name || "");
        setDocuments(d);
      })
      .catch(() => {
        if (!cancelled) setError("문서 또는 페르소나를 불러오지 못했습니다");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (error) {
    return <p style={{ fontSize: 13, color: "var(--color-accent-700)" }}>{error}</p>;
  }
  if (!personas || !documents) {
    return <p style={{ fontSize: 13, color: "var(--color-neutral-600)" }}>불러오는 중…</p>;
  }

  const persona = personas.find((p) => p.name === personaName) ?? personas[0];
  // "338" 을 적어두지 않는다 — 코퍼스가 바뀌면 이 숫자도 바뀐다.
  const totalChunks = documents.reduce((sum, d) => sum + d.chunk_count, 0);

  return (
    <div style={{ maxWidth: 1240, display: "flex", flexDirection: "column", gap: 20 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 14, flexWrap: "wrap" }}>
        <span style={{ fontSize: 13, color: "var(--color-neutral-700)" }}>
          현재 페르소나 기준 가시성으로 표시합니다
        </span>
        <div style={{ display: "flex", border: "1px solid var(--color-divider)" }}>
          {personas.map((p) => {
            const on = p.name === persona.name;
            return (
              <button
                key={p.name}
                type="button"
                onClick={() => setPersonaName(p.name)}
                style={{
                  padding: "7px 13px",
                  background: on ? "var(--color-accent)" : "transparent",
                  border: 0,
                  borderRight: "1px solid var(--color-divider)",
                  fontSize: 12.5,
                  cursor: "pointer",
                  color: on ? "var(--color-bg)" : "var(--color-text)",
                  fontFamily: "var(--font-body)",
                }}
              >
                {p.name}
              </button>
            );
          })}
        </div>
        <span style={{ flex: 1 }} />
        <span className="tag tag-neutral">
          코퍼스 {totalChunks} 청크 / {totalChunks} chunks
        </span>
      </div>

      <DocumentTable documents={documents} persona={persona} />

      <p style={{ margin: 0, fontSize: 12.5, lineHeight: 1.6, color: "var(--color-neutral-700)", maxWidth: 760 }}>
        허용 부서가 비어 있으면 전사 공개입니다 — &quot;아무도 못 본다&quot;가 아닙니다. ISMS-P 안내서는 본문이
        실제 공개 표준이고 권한 등급만 부여했으며, 사내 규정 문서와 시연 계정은 합성입니다.
      </p>
      <p style={{ margin: 0, fontSize: 12.5, lineHeight: 1.6, color: "var(--color-neutral-700)", maxWidth: 760 }}>
        이 가시성 계산은 SQL(chunk_search._권한_WHERE) · 파이썬(core/access/visibility.py)에 이은 세 번째
        사본입니다. 이 화면의 계산은 표시용이고, 실제 강제는 서버의 SQL 이 합니다.
      </p>
    </div>
  );
}
