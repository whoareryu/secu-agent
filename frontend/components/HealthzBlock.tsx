"use client";

import { useEffect, useState } from "react";
import type { HealthzResponse } from "@/lib/types";

// GET /healthz 를 BFF 경유로 실제 호출한다 — 지어낸 "db true · model ready"
// 를 적지 않는다. Sidebar.tsx(구 앱 셸)에 있던 것과 같은 컴포넌트다 —
// Sidebar.tsx 는 Task 7 에서 사라지므로 지금은 그 파일을 건드리지 않고
// 여기 새로 옮겨, 설명 면(SurfaceNav)이 판단해 쓸 수 있게 한다.
export default function HealthzBlock() {
  const [health, setHealth] = useState<HealthzResponse | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetch("/api/healthz")
      .then((r) => {
        if (!r.ok) throw new Error(`healthz ${r.status}`);
        return r.json() as Promise<HealthzResponse>;
      })
      .then((data) => {
        if (!cancelled) setHealth(data);
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div
      style={{
        marginTop: "auto",
        padding: 20,
        borderTop: "1px solid var(--color-on-accent-divider)",
        display: "flex",
        flexDirection: "column",
        gap: 8,
      }}
    >
      <div style={{ fontSize: 10, letterSpacing: ".16em", textTransform: "uppercase", color: "var(--color-on-accent-faint)" }}>
        GET /healthz
      </div>
      {failed ? (
        <div style={{ fontSize: 12.5, color: "var(--color-on-accent-danger)" }}>연결 실패 / unreachable</div>
      ) : !health ? (
        <div style={{ fontSize: 12.5, color: "var(--color-on-accent-muted)" }}>확인 중… / checking…</div>
      ) : (
        <>
          <HealthzRow label="db" value={String(health.db)} accent />
          <HealthzRow label="model" value={health.model} accent />
          <HealthzRow label="status" value={health.status} />
        </>
      )}
    </div>
  );
}

function HealthzRow({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12.5 }}>
      <span style={{ color: "var(--color-on-accent-muted)" }}>{label}</span>
      <span style={accent ? { color: "var(--color-on-accent-ok)" } : undefined}>{value}</span>
    </div>
  );
}
