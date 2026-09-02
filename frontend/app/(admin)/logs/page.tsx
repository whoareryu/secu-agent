"use client";

import { useEffect, useState } from "react";
import Blueprint from "@/components/Blueprint";
import PersonaSegment, { type Principal } from "@/components/PersonaSegment";

type LogEvent = {
  id: number;
  ts: string | null;
  host: string;
  process: string | null;
  event_type: string;
  raw: string;
};

// 이 화면에 주체 선택기가 있는 이유: 저장소에 **권한 필터를 우회하는 로그
// 조회 경로가 없다**(core/ports.py 의 LogSearch.query 가 Principal 을 필수로
// 받는다 — "권한 없는 조회를 호출할 방법이 없다"). 관리자 편의로 하나
// 만들면 그것이 이 프로젝트가 테스트로 막아온 그 경로다
// (backend/tests/test_api_log_events.py). 직원 면에서 선택기를 걷어낸 것과
// 모순되지 않는다 — 직원 면은 한 사람이 되어보는 곳이고 여기는 장치를
// 들여다보는 곳이라 도구가 다르다(app/(explain)/documents/page.tsx 의
// 선택기와 같은 이유).
export default function LogsPage() {
  const [계정, set계정] = useState<Principal[]>([]);
  const [계정오류, set계정오류] = useState<string | null>(null);
  const [주체, set주체] = useState("");
  const [이벤트, set이벤트] = useState<LogEvent[] | null>(null);
  const [이벤트오류, set이벤트오류] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetch("/api/principals")
      .then((r) => {
        if (!r.ok) throw new Error(`principals ${r.status}`);
        return r.json() as Promise<Principal[]>;
      })
      .then((p) => {
        if (cancelled) return;
        set계정(p);
        set주체((prev) => prev || p[0]?.name || "");
      })
      .catch(() => {
        if (!cancelled) set계정오류("주체 목록을 불러오지 못했습니다 — 백엔드가 잠들어 있을 수 있습니다.");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!주체) return;
    let cancelled = false;
    set이벤트(null);
    set이벤트오류(null);
    fetch(`/api/log-events?persona=${encodeURIComponent(주체)}`)
      .then((r) => {
        if (!r.ok) throw new Error(`log-events ${r.status}`);
        return r.json() as Promise<LogEvent[]>;
      })
      .then((data) => {
        if (!cancelled) set이벤트(data);
      })
      .catch(() => {
        // 실패와 0건은 다른 사실이다 — 0건은 "이 주체가 볼 수 있는
        // 호스트에 이벤트가 없다"는 것이고, 실패는 "몰라서 못 보여준다"는
        // 것이다. 여기서 이벤트를 [] 로 채우면 둘이 화면에서 똑같아 보여서
        // 뒤쪽 사실이 앞쪽 사실인 척하게 된다(AccessTable.tsx·
        // AlertTable.tsx 가 같은 이유로 error 상태를 따로 둔다). 백엔드는
        // 켜져 있을 때만 응답하는 배포라 이 경로는 실제로 자주 밟힌다.
        if (!cancelled) set이벤트오류("로그를 불러오지 못했습니다 — 백엔드가 잠들어 있을 수 있습니다.");
      });
    return () => {
      cancelled = true;
    };
  }, [주체]);

  return (
    <div style={{ maxWidth: 1100, display: "flex", flexDirection: "column", gap: 18 }}>
      <p style={{ margin: 0, fontSize: 13.5, lineHeight: 1.7, color: "var(--color-neutral-700)" }}>
        주체를 바꾸면 보이는 이벤트가 달라집니다. 다만 이건 그 주체의 로그가 아니라{" "}
        <strong>그 주체가 볼 수 있는 호스트의 로그</strong>입니다 — 권한은 호스트 단위로 걸리므로, 같은
        호스트 안에는 다른 사람이 남긴 기록도 함께 섞여 있을 수 있습니다. 이 화면의 실제 강제는{" "}
        <code>log_search.py</code> 의 SQL JOIN 이 합니다 — 권한 밖 호스트의 행은 조인에서부터 빠집니다
        (검사가 아니라 구조로 닫힙니다). 그 SQL 이 쓰는 <code>permission_sql.py</code> 의{" "}
        <code>권한_WHERE()</code> 는 문서 검색(<code>chunk_search.py</code>)과 공유하는 함수이고,{" "}
        <code>core/access/visibility.py</code> 의 <code>visible()</code> 은 그 판정의 파이썬 쪽 문서화된
        사본입니다 — 같은 규칙이 문서와 로그 양쪽을 다스립니다.
      </p>
      {계정오류 ? (
        <p style={{ fontSize: 13, color: "var(--color-accent-700)" }}>{계정오류}</p>
      ) : (
        <PersonaSegment personas={계정} value={주체} onChange={set주체} />
      )}
      {이벤트오류 ? (
        <p style={{ fontSize: 13, color: "var(--color-accent-700)" }}>{이벤트오류}</p>
      ) : 이벤트 === null ? (
        <p style={{ fontSize: 13, color: "var(--color-neutral-600)" }}>불러오는 중…</p>
      ) : (
        <>
          <div style={{ fontSize: 13 }}>{주체} 가 볼 수 있는 호스트의 로그 {이벤트.length}건</div>
          {이벤트.length === 0 ? (
            <p style={{ fontSize: 13, color: "var(--color-neutral-600)" }}>
              이 주체가 볼 수 있는 호스트에 기록된 이벤트가 없습니다.
            </p>
          ) : (
            이벤트.map((e) => (
              <Blueprint key={e.id} className="card" style={{ padding: 14 }}>
                <div style={{ fontSize: 12, color: "var(--color-neutral-700)" }}>
                  {e.ts ?? "시각 없음"} · {e.host} · {e.event_type}
                </div>
                <div style={{ fontFamily: "ui-monospace,monospace", fontSize: 12.5, marginTop: 6 }}>{e.raw}</div>
              </Blueprint>
            ))
          )}
        </>
      )}
    </div>
  );
}
