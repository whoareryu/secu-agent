import EvidencePanel from "@/components/EvidencePanel";

// 이 화면은 "어떻게 동작하는가"를 설명이 아니라 실행으로 보여주는 자리다.
// 그래서 규칙이 하나 더 붙는다 — 뒷받침 없는 문장을 한 줄도 두지 않는다.
// 네 패널 모두 EvidencePanel 을 거치므로 evidence 와 (measured 면) source 를
// 빠뜨리면 컴파일이 막힌다.
//
// 패널 ①②는 Task 5·6 이 라이브/2단계 인용으로 갈아끼우고, 패널 ④는 W4a
// 로그 적재 이후 Task 7 이 채운다. 지금은 이 저장소에서 실제로 확인한
// 만큼만 적는다.
export default function HowPage() {
  return (
    <div style={{ maxWidth: 1000, display: "flex", flexDirection: "column", gap: 22 }}>
      <EvidencePanel
        evidence="measured"
        source="backend/tests/test_naive_leaks.py · POST /demo/compare 실측(2026-09-01)"
        kicker="라이브 누출 시연"
        title="사전 필터링 대 순진한 사후 필터링"
      >
        <p style={{ margin: 0, fontSize: 13, lineHeight: 1.65, color: "var(--color-neutral-700)" }}>
          같은 질의를 사전 필터링 경로와 순진한(사후 필터링) 경로 양쪽에 돌리면 개수가 갈립니다. 질의
          &quot;임원 성과급은 어떤 기준으로 정해지나&quot;, k=10 에서 사전 필터링은 김개발·박인사·최임원 모두
          10/10/10, 순진한 경로는 김개발 7 · 박인사 7 · 최임원 10 입니다. 등급이 낮을수록 순진한 경로에서
          결과가 줄어드는 것 자체가 &quot;내가 못 보는 곳에 이 질의와 가까운 문서가 있다&quot;는 존재 누출입니다.
        </p>
      </EvidencePanel>

      <EvidencePanel
        evidence="measured"
        source="backend/adapters/db/chunk_search.py (by_vector 독스트링) · backend/tests/test_leakage.py"
        kicker="2단계 누출"
        title="필터를 걸어도 플래너가 인라인하면 다시 샌다"
      >
        <p style={{ margin: 0, fontSize: 13, lineHeight: 1.65, color: "var(--color-neutral-700)" }}>
          사전 필터링 SQL 은 WITH 절(CTE)로 권한 통과 청크를 먼저 확정합니다. <code>AS MATERIALIZED</code>{" "}
          힌트가 빠지면 Postgres 플래너가 이 CTE 를 인라인해 근사 벡터 인덱스(HNSW)를 먼저 타고 권한 필터를
          나중에 적용합니다 — 그 순간 사전 필터링이 다시 사후 필터링이 됩니다. 실측(pgvector:pg16, 공개
          2,000 + 기밀 2,000 청크): 인라인되면 등급 1 사용자가 k=10 을 요청해도 0건, <code>AS MATERIALIZED</code>{" "}
          를 붙이면 10건이 옵니다. 지금 <code>chunk_search.py</code> 의 검색 SQL 은{" "}
          <code>AS MATERIALIZED</code> 를 쓰고 있어 이 경로가 막혀 있습니다.
        </p>
      </EvidencePanel>

      <EvidencePanel evidence="schema" kicker="기록이 담지 않는 것" title="access_records 는 본문도 제목도 담지 않는다">
        <p style={{ margin: 0, fontSize: 13, lineHeight: 1.65, color: "var(--color-neutral-700)" }}>
          <code>access_records</code> 테이블에는 청크 본문도 문서 제목도 담는 컬럼이 없습니다
          (backend/db/schema.sql) — 담긴 것은 id · ts 같은 식별자와 persona, department, clearance,
          query, clause_code, resource_kind, resource_id, allowed 같은 신원·판정 값입니다. 제목을 빼는
          이유는 제목만으로도 문서의 존재가 드러나기 때문입니다. resource_kind 는{" "}
          <code>chunk</code> 또는 <code>log_event</code> 만 허용하는 CHECK 제약이 있고 DEFAULT 가 없어, 종류를
          빠뜨린 INSERT 가 조용히 청크로 기록되는 일을 막습니다.
        </p>
      </EvidencePanel>

      <EvidencePanel
        evidence="schema"
        kicker="같은 불변식, 두 데이터 타입"
        title="문서와 로그가 같은 권한 판정을 공유한다"
      >
        <p style={{ margin: 0, fontSize: 13, lineHeight: 1.65, color: "var(--color-neutral-700)" }}>
          <code>documents</code> 와 로그가 발생한 장비를 담는 <code>hosts</code> 는 같은 두 권한 컬럼{" "}
          <code>required_clearance</code> · <code>allowed_departments</code> 를 갖습니다(backend/db/schema.sql).
          이름을 맞춘 이유는 <code>core/access/visibility.py</code> 의 <code>visible()</code> 하나를 문서와
          로그가 그대로 공유하기 위해서입니다 — 판정 함수가 두 벌이면 그 어긋남은 조용히 결과만 줄이고
          에러를 내지 않습니다. <code>log_events</code> 테이블 자체는 스키마만 있고 적재는 아직 없습니다.
        </p>
      </EvidencePanel>
    </div>
  );
}
