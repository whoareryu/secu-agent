import Blueprint from "@/components/Blueprint";

// W4 계획 화면 — 아직 아무것도 적재되지 않는다는 것을 그대로 보여준다.
// 로그 파이프라인이 W4 에서 붙기 전까지 이 화면은 손대지 않는다
// (design source: docs/handoff/prototype.dc.html, isLogs 블록).
export default function LogsPage() {
  return (
    <div style={{ maxWidth: 1240, display: "flex", flexDirection: "column", gap: 20 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <span className="tag tag-outline">W4 계획 / Planned</span>
        <span style={{ fontSize: 13, color: "var(--color-neutral-700)" }}>
          log_events 스키마는 이미 있고 적재는 W4 에서 채웁니다 — 나중에 마이그레이션하지 않기 위해서입니다.
        </span>
      </div>
      <div style={{ display: "flex", gap: 10, opacity: 0.5, pointerEvents: "none" }}>
        <input className="input" style={{ maxWidth: 280 }} placeholder="host / principal 검색" disabled />
        <button className="btn btn-secondary" disabled>
          event_type
        </button>
        <button className="btn btn-secondary" disabled>
          severity
        </button>
        <button className="btn btn-secondary" disabled>
          최근 24시간
        </button>
      </div>
      <Blueprint className="card" style={{ padding: 20, gap: 16 }}>
        <table className="table">
          <thead>
            <tr>
              <th>ts</th>
              <th>host</th>
              <th>process</th>
              <th>event_type</th>
              <th>principal_name</th>
              <th>severity</th>
              <th>raw</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td
                colSpan={7}
                style={{ padding: "56px 0", textAlign: "center", color: "var(--color-neutral-600)", fontSize: 13.5 }}
              >
                적재된 이벤트가 없습니다 / No events ingested
                <br />
                <span style={{ fontSize: 12 }}>로그 파이프라인과 이상탐지 리포트는 W4 범위입니다.</span>
              </td>
            </tr>
          </tbody>
        </table>
      </Blueprint>
      <Blueprint className="card" style={{ padding: 20, gap: 10 }}>
        <div className="card-kicker">table log_events</div>
        <div
          style={{
            fontFamily: "ui-monospace,monospace",
            fontSize: 12.5,
            lineHeight: 1.85,
            color: "var(--color-accent-800)",
          }}
        >
          id BIGSERIAL · ts TIMESTAMPTZ · host TEXT NOT NULL · process TEXT · event_type TEXT NOT NULL ·
          principal_name TEXT · raw TEXT NOT NULL · severity TEXT
        </div>
        <p style={{ margin: 0, fontSize: 12.5, color: "var(--color-neutral-700)" }}>
          raw 는 원본을 그대로 보존합니다. 인덱스는 ts 와 event_type 에 있습니다.
        </p>
      </Blueprint>
    </div>
  );
}
