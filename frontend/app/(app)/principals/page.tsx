"use client";

import { useEffect, useState } from "react";
import PrincipalTable from "@/components/PrincipalTable";
import Blueprint from "@/components/Blueprint";
import type { Principal } from "@/components/PersonaSegment";

// 세 페르소나는 하드코딩하지 않는다 — GET /api/principals 가 principals
// 테이블을 그대로 중계한다.
export default function PrincipalsPage() {
  const [personas, setPersonas] = useState<Principal[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetch("/api/principals")
      .then((r) => {
        if (!r.ok) throw new Error(`principals ${r.status}`);
        return r.json() as Promise<Principal[]>;
      })
      .then((data) => {
        if (!cancelled) setPersonas(data);
      })
      .catch(() => {
        if (!cancelled) setError("페르소나를 불러오지 못했습니다");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (error) {
    return <p style={{ fontSize: 13, color: "var(--color-accent-700)" }}>{error}</p>;
  }
  if (!personas) {
    return <p style={{ fontSize: 13, color: "var(--color-neutral-600)" }}>불러오는 중…</p>;
  }

  return (
    <div style={{ maxWidth: 1000, display: "flex", flexDirection: "column", gap: 22 }}>
      <PrincipalTable principals={personas} current={personas[0]?.name ?? ""} />
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 22 }}>
        <Blueprint className="card" style={{ padding: 20, gap: 12 }}>
          <div className="card-kicker">Seed</div>
          <div
            style={{
              fontFamily: "ui-monospace,monospace",
              fontSize: 12.5,
              padding: 12,
              border: "1px solid var(--color-divider)",
              color: "var(--color-accent-800)",
            }}
          >
            python -m pipeline.cli seed-principals
          </div>
          <p style={{ margin: 0, fontSize: 13, lineHeight: 1.6, color: "var(--color-neutral-700)" }}>
            data/principals.json 의 세 계정을 principals 테이블에 넣습니다.
          </p>
        </Blueprint>
        <Blueprint className="card" style={{ padding: 20, gap: 12 }}>
          <div className="card-kicker">사칭 경로가 없는 이유</div>
          <p style={{ margin: 0, fontSize: 13, lineHeight: 1.65, color: "var(--color-neutral-700)" }}>
            AskRequest 에는 department·clearance 가 없습니다. 클라이언트가 그 값을 보낼 수 있으면 그것이 곧
            사칭 경로입니다. 서버가 페르소나 이름을 받아 principals 테이블에서 번역합니다. 없는 이름에는
            &quot;알 수 없는 페르소나&quot;만 돌려주고 어떤 이름이 존재하는지 알려주지 않습니다.
          </p>
        </Blueprint>
      </div>
    </div>
  );
}
