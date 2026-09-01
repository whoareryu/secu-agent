"use client";

import { useEffect, useState } from "react";
import AskPanel from "@/components/AskPanel";
import RightRail from "@/components/RightRail";
import type { Principal } from "@/components/PersonaSegment";

// 세 페르소나는 하드코딩하지 않는다 — GET /api/principals 가 백엔드
// principals 테이블을 그대로 중계하므로 계정을 늘리면 화면이 따라온다.
export default function AskPage() {
  const [personas, setPersonas] = useState<Principal[] | null>(null);
  const [personasError, setPersonasError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [persona, setPersona] = useState("");

  useEffect(() => {
    let cancelled = false;
    fetch("/api/principals")
      .then((r) => {
        if (!r.ok) throw new Error(`principals ${r.status}`);
        return r.json() as Promise<Principal[]>;
      })
      .then((data) => {
        if (cancelled) return;
        setPersonas(data);
        setPersona((prev) => prev || data[0]?.name || "");
      })
      .catch(() => {
        if (!cancelled) setPersonasError("페르소나를 불러오지 못했습니다");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "minmax(0,1fr) 320px",
        gap: 32,
        alignItems: "start",
        maxWidth: 1240,
      }}
    >
      <AskPanel
        personas={personas}
        personasError={personasError}
        query={query}
        onQueryChange={setQuery}
        persona={persona}
        onPersonaChange={setPersona}
      />
      <RightRail personas={personas} query={query} onSelectSample={setQuery} />
    </div>
  );
}
