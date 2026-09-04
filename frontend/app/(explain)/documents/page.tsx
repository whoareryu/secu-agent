"use client";

import { useEffect, useState } from "react";
import DocumentTable, { type Document } from "@/components/DocumentTable";
import type { Principal } from "@/components/PersonaSegment";
import { personaFrom } from "@/lib/persona";

// 페르소나 3명은 하드코딩하지 않는다 — GET /api/principals 를 그대로 쓴다.
// 문서는 GET /api/documents 가 권한 필터 없이 전부 돌려준다: 이 화면은
// "규칙이 어떻게 적용되는지"를 보여주는 자리이므로 가시성을 페르소나별로
// 클라이언트가 계산한다(lib/visibility.ts 의 visible() — DocumentTable.tsx 는
// 기존 import 경로가 깨지지 않게 재수출만 한다).
//
// 페르소나 선택기를 지우지 않는다 — /ask(직원 면)는 "내가 그 사람이 되어"
// 쓰는 자리라 선택기가 없지만, 여기는 "누가 무엇을 보는가"를 비교하는
// 자리라 주체를 바꿔보는 것 자체가 이 화면의 일이다. 감사 로그(Task 9)의
// 선택기도 같은 이유로 남는다.
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
      // 세션 페르소나. 실패해도 화면을 못 쓰게 만들지 않는다 — 첫 값이
      // 없을 뿐이므로 null 로 떨어뜨리고 목록의 첫 사람으로 시작한다.
      fetch("/api/persona")
        .then((r) => (r.ok ? (r.json() as Promise<{ name: string | null }>) : { name: null }))
        .catch(() => ({ name: null })),
    ])
      .then(([p, d, 세션]) => {
        if (cancelled) return;
        setPersonas(p);
        // 첫 값은 지금 보고 있는 직원이다. p[0] 로 시작하면 허브에서
        // 한보안을 고르고 온 사람에게 이 화면이 김개발의 가시성을
        // 보여주면서 "현재 페르소나 기준" 이라고 적게 된다.
        const 세션이름 = personaFrom(세션.name ?? undefined, p.map((x) => x.name));
        setPersonaName((prev) => prev || 세션이름 || p[0]?.name || "");
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
          아래에서 고른 계정 기준으로 표시합니다
        </span>
        {/* PersonaSegment 와 같은 모양이되(app/_ds/industry.css 의 .seg) 이름만
            담는 촘촘한 판이라 클래스를 쓰지 않고 여기서 그린다 — 저쪽은
            부서·등급까지 두 줄로 담아 높이가 다르다. */}
        <div
          role="group"
          aria-label="기준 계정"
          style={{
            display: "flex",
            flexWrap: "wrap",
            gap: 4,
            padding: 4,
            background: "var(--color-neutral-100)",
            border: "1px solid var(--color-neutral-200)",
            borderRadius: "var(--radius-md)",
          }}
        >
          {personas.map((p) => {
            const on = p.name === persona.name;
            return (
              <button
                key={p.name}
                type="button"
                aria-pressed={on}
                onClick={() => setPersonaName(p.name)}
                style={{
                  padding: "7px 13px",
                  background: on ? "var(--color-surface)" : "transparent",
                  border: 0,
                  borderRadius: "var(--radius-sm)",
                  boxShadow: on ? "var(--shadow-sm)" : undefined,
                  fontSize: 13,
                  fontWeight: on ? 600 : 500,
                  cursor: "pointer",
                  color: on ? "var(--color-text)" : "var(--color-neutral-700)",
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

      {/* 이 문단이 없으면 이 화면은 /my/documents 와 모순으로 읽힌다. 저쪽은
          "목록에 없는 문서는 제목조차 브라우저에 오지 않습니다" 라고 적는데
          여기는 못 보는 문서의 제목을 대놓고 보여주기 때문이다. 둘 다 참인
          이유를 화면이 직접 말한다.
          backend/tests/test_document_screen_claims.py 가 이 문단의 존재를
          고정한다 — 주석은 세지 않는다. */}
      <p
        style={{
          margin: 0,
          fontSize: 12.5,
          lineHeight: 1.7,
          color: "var(--color-neutral-800)",
          maxWidth: 760,
          borderLeft: "2px solid var(--color-accent-400)",
          paddingLeft: 10,
        }}
      >
        <strong>문서 카탈로그를 권한 필터 없이 브라우저로 받는 화면은 여기 하나입니다.</strong>{" "}
        그래야 못 보는 문서가 &quot;가려짐&quot; 행으로 존재할 수 있고, 계정을 바꿔가며 무엇이 갈리는지
        비교할 수 있습니다 — 규칙을 장치 밖에서 보여주는 자리이기 때문입니다. 답변 경로(<code>/ask</code>)와{" "}
        <code>내 문서</code>는 반대로 서버에서 걸러, 못 보는 문서는 제목조차 브라우저로 내려가지 않습니다.
      </p>
      <p style={{ margin: 0, fontSize: 12.5, lineHeight: 1.6, color: "var(--color-neutral-700)", maxWidth: 760 }}>
        그렇게 해도 되는 이유는 이 표의 {documents.length}행 어느 것도 감출 것이 없기 때문입니다. 사내
        규정 {documents.filter((d) => d.doc_type === "md").length}건은{" "}
        <strong>합성</strong>이고 <code>data/policies/</code> 에 본문·머리말째 커밋돼 있어, 등급 3 문서도{" "}
        <code>clearance: 3</code> 이 적힌 채 <strong>공개 저장소</strong>에서 그대로 읽힙니다. 남은 한 행인
        ISMS-P 안내서는 등급 1 · 전사 공개라 애초에 가려지는 계정이 없습니다(PDF 본체는 저장소에 없고{" "}
        <code>data/raw/</code> 로 따로 받습니다). 실제 사내 규정이었다면 이 화면은 이렇게 만들 수 없습니다.
      </p>
      <p style={{ margin: 0, fontSize: 12.5, lineHeight: 1.6, color: "var(--color-neutral-700)", maxWidth: 760 }}>
        허용 부서가 비어 있으면 전사 공개입니다 — &quot;아무도 못 본다&quot;가 아닙니다. ISMS-P 안내서는 본문이
        실제 공개 표준이고 권한 등급만 부여했습니다.
      </p>
      <p style={{ margin: 0, fontSize: 12.5, lineHeight: 1.6, color: "var(--color-neutral-700)", maxWidth: 760 }}>
        이 가시성 계산은 SQL(chunk_search._권한_WHERE) · 파이썬(core/access/visibility.py)에 이은 세 번째
        사본입니다. 이 화면의 계산은 표시용이고, 실제 강제는 서버의 SQL 이 합니다.
      </p>
    </div>
  );
}
