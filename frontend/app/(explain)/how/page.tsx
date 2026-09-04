import EvidencePanel from "@/components/EvidencePanel";
import LeakCompare from "@/components/LeakCompare";

// 이 화면은 "어떻게 동작하는가"를 설명이 아니라 실행으로 보여주는 자리다.
// 그래서 규칙이 하나 더 붙는다 — 뒷받침 없는 문장을 한 줄도 두지 않는다.
// 네 패널 모두 EvidencePanel 을 거치므로 evidence 와 (measured 면) source 를
// 빠뜨리면 컴파일이 막힌다.
//
// 패널 ②③은 Task 6 이 2단계 누출과 기록 스키마로 채웠다. 패널 ④는 W4a
// 로그 적재 이후 Task 7 이 채웠다. 지금은 이 저장소에서 실제로 확인한
// 만큼만 적는다.
export default function HowPage() {
  return (
    <div style={{ maxWidth: 1000, display: "flex", flexDirection: "column", gap: 22 }}>
      <EvidencePanel evidence="live" kicker="라이브 누출 시연" title="사전 필터링 대 순진한 사후 필터링">
        <LeakCompare />
      </EvidencePanel>

      <EvidencePanel
        evidence="measured"
        source="backend/adapters/db/chunk_search.py (by_vector 독스트링) · backend/tests/test_leakage.py:30-35 (문서당_청크 상수와 주석)"
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
        <p style={{ margin: 0, fontSize: 13, lineHeight: 1.65, color: "var(--color-neutral-700)" }}>
          이 수치는 코퍼스 규모에 좌우됩니다. <code>test_leakage.py</code> 의 고정값{" "}
          <code>문서당_청크</code> 는 2,000 입니다 — 문서당 300 개(총 600)로 줄이면 인라인해도 여전히 10건이
          나와 누출이 드러나지 않고, 2,000 개(총 4,000)여야 인라인 시 0건이 됩니다. 600 규모에서는 플래너가
          인라인해도 순차 스캔으로 정확 검색을 해버려 근사 인덱스의 후보 절단이 애초에 일어나지 않기
          때문입니다. 지금 작업 코퍼스는 문서 9개 · 청크 338개로, 이 현상이 나타나는 규모가 아닙니다 —
          그래서 이 패널은 라이브가 아니라 measured 입니다.
        </p>
        <p
          style={{
            margin: 0,
            fontSize: 13,
            lineHeight: 1.65,
            color: "var(--color-neutral-700)",
            borderLeft: "2px solid var(--color-accent-400)",
            paddingLeft: 10,
          }}
        >
          위 패널(①)은 &quot;이렇게 짜면 샌다&quot; 를 보여줍니다. 이 패널은{" "}
          <strong>&quot;고친 줄 알았는데 여전히 샜다&quot;</strong> 를 보여줍니다 —{" "}
          <code>AS MATERIALIZED</code> 로 고쳤다고 믿은 뒤에도 코퍼스 규모가 바뀌면 같은 취약점이 다시
          드러납니다. 두 번째는 테스트 없이는 알 수 없습니다.
        </p>
      </EvidencePanel>

      <EvidencePanel evidence="schema" kicker="기록이 담지 않는 것" title="access_records 는 본문도 제목도 담지 않는다">
        <p style={{ margin: 0, fontSize: 13, lineHeight: 1.65, color: "var(--color-neutral-700)" }}>
          <code>access_records</code> 의 컬럼 전부입니다(backend/db/schema.sql):
        </p>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
          {[
            "id",
            "ts",
            "persona",
            "department",
            "clearance",
            "query",
            "clause_code",
            "resource_kind",
            "resource_id",
            "allowed",
          ].map((컬럼) => (
            <span key={컬럼} className="tag tag-outline" style={{ fontSize: 11.5 }}>
              {컬럼}
            </span>
          ))}
        </div>
        <p style={{ margin: 0, fontSize: 13, lineHeight: 1.65, color: "var(--color-neutral-700)" }}>
          청크 본문도 문서 제목도 담는 컬럼이 없습니다 — <code>text</code>, <code>doc_title</code>,{" "}
          <code>title</code>, <code>body</code>, <code>content</code> 다섯 이름 전부 없습니다. 제목만으로도
          문서의 존재가 드러나기 때문입니다 — <code>AccessViolation</code> 이 예외 메시지에 식별자만 담고
          본문·호스트 이름·문서 제목을 담지 않는 것과 같은 원칙입니다(core/agent/policy.py). 컬럼을 더하면
          실패하는 테스트가 하나 있습니다:{" "}
          <code>backend/tests/test_access_log.py::test_기록에_본문_컬럼이_없다</code>.
        </p>
        <p style={{ margin: 0, fontSize: 13, lineHeight: 1.65, color: "var(--color-neutral-700)" }}>
          열람 대상은 청크이거나 로그 이벤트입니다. <code>resource_kind</code> 는{" "}
          <code>chunk</code> 또는 <code>log_event</code> 만 허용하는 CHECK 제약이 있고 DEFAULT 가 없어, 종류를
          빠뜨린 INSERT 가 조용히 청크로 기록되는 일을 막습니다. 이 컬럼이 필요한 이유는 두 id 공간이
          겹치기 때문입니다 — 청크 id(1..338)와 로그 이벤트 id(1..33). <code>resource_kind</code> 없이 숫자만
          두면 로그 위반 기록이 무관한 문서 청크로 풀립니다 — W4a 최종 리뷰가 실제로 잡은 결함입니다.
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
          에러를 내지 않습니다.
        </p>
        <div className="table-scroll">
        <table className="table">
          <thead>
            <tr>
              <th></th>
              <th>문서</th>
              <th>로그</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>관측되는 값</td>
              <td>결과 개수 (k 가 상한)</td>
              <td>이벤트 개수 (가변)</td>
            </tr>
            <tr>
              <td>위험</td>
              <td>개수 차이로 존재 노출</td>
              <td>부분 집계를 전체로 오해</td>
            </tr>
            <tr>
              <td>장치</td>
              <td>사전 필터링 + 고정 k</td>
              <td>사전 필터링 + 무조건적 범위 고지</td>
            </tr>
          </tbody>
        </table>
        </div>
        <p style={{ margin: 0, fontSize: 13, lineHeight: 1.65, color: "var(--color-neutral-700)" }}>
          로그 쪽 장치는 <code>core/agent/policy.py</code> 의 <code>로그_범위_고지</code> 문구입니다 — 숨겨진
          이벤트가 1000건이든 0건이든 같은 문구가 붙어, 관측값이 숨은 데이터 유무에 따라 변하지 않습니다.
          문서 쪽처럼 개수를 숨기는 것이 아니라 부분 집계라는 사실 자체를 알리는 장치입니다 — 관측되는 값의
          성질이 다르기 때문에 장치의 모양도 다릅니다.
        </p>
        <p style={{ margin: 0, fontSize: 13, lineHeight: 1.65, color: "var(--color-neutral-700)" }}>
          <code>visible()</code> 을 부르는 비테스트 호출부는 <code>core/agent/policy.py</code> 안에 둘입니다 —
          62행이 청크 히트 재검증, 98행이 로그 이벤트 재검증입니다. 같은 함수가 서로 다른 두 타입을 재검증하는
          것이 이 패널의 주장입니다. 이 둘도{" "}
          <code>backend/tests/test_how_screen_claims.py</code> 가 집합 동일성으로 고정합니다.
        </p>
        <p style={{ margin: 0, fontSize: 13, lineHeight: 1.65, color: "var(--color-neutral-700)" }}>
          권한 SQL 조각도 한 곳에서 옵니다 — <code>adapters/db/permission_sql.py</code> 의{" "}
          <code>권한_WHERE(alias)</code> 하나입니다. 이를 직접 import 하는 파일은 여섯입니다 — 문서 검색(
          <code>chunk_search.py</code>), 로그 검색(<code>log_search.py</code>),{" "}
          <strong>의도적으로 새는 데모 경로</strong>(<code>demo/naive_search.py</code>), 위 패널 ①의 조항 코드
          조회(<code>demo/compare.py</code>), 그리고 테스트 둘(
          <code>backend/tests/test_permission_sql.py</code> ·{" "}
          <code>backend/tests/test_search_sql.py</code>) 입니다 —{" "}
          <code>
            grep -rn &quot;from adapters.db.permission_sql import 권한_WHERE&quot; backend --include=&quot;*.py&quot;
          </code>{" "}
          를 돌리면 이 여섯 줄이 그대로 나옵니다. 비테스트 넷 중 사본을 따로 두는 것은{" "}
          <code>chunk_search.py</code> 뿐입니다 — 40행이{" "}
          <code>_권한_WHERE = 권한_WHERE(&quot;d&quot;)</code> 로 모듈 상수에 저장해 둡니다.{" "}
          <code>log_search.py</code>:34 · <code>naive_search.py</code>:40 · <code>compare.py</code>:57 은 반환값을
          호출부 문자열에 바로 끼워 넣을 뿐 저장해두는 사본이 없습니다.{" "}
          <code>test_permission_sql.py</code> 의 <code>test_chunk_search_가_이_조각을_쓴다</code> 가 그 저장된
          사본이 원본과 여전히 같은지를 단언하고, <code>test_search_sql.py</code> 는 권한 조건을 담은 SQL 네
          문장이 그 조각을 여전히 포함하는지와 그 위치가 <code>ORDER BY</code>·<code>LIMIT</code> 보다 앞인지를
          단언합니다 — 뒤로 밀리는 순간 사후 필터링이기 때문입니다. 이 목록과 행 번호는{" "}
          <code>backend/tests/test_how_screen_claims.py</code> 가 집합 동일성으로 고정합니다 — 일곱째 파일이
          생기면 이 문장이 조용히 거짓이 되는 대신 테스트가 먼저 터집니다.
        </p>
        <p
          style={{
            margin: 0,
            fontSize: 13,
            lineHeight: 1.65,
            color: "var(--color-neutral-700)",
            borderLeft: "2px solid var(--color-accent-400)",
            paddingLeft: 10,
          }}
        >
          가장 좋은 사실: 위 패널(①)의 새는 데모 경로도 <strong>같은 권한 조각</strong>을 씁니다. 그 경로가 새는
          이유는 규칙이 달라서가 아니라, <code>naive_search.py</code> 에서는 이 조각이 상위 k개를 먼저 뽑는{" "}
          <code>ORDER BY</code> · <code>LIMIT</code> 서브쿼리 <strong>바깥</strong>에 놓여 사후 필터가 되기
          때문입니다 — 사전 필터링 버전(<code>chunk_search.py</code>)은 같은 조각을 서브쿼리 <strong>안</strong>
          에 둡니다.
        </p>
        <p style={{ margin: 0, fontSize: 13, lineHeight: 1.65, color: "var(--color-neutral-600)" }}>
          한 곳인 것은 이 <strong>SQL 조각</strong>이지 권한 <strong>규칙</strong> 자체가 아닙니다.{" "}
          <code>permission_sql.py</code> 의 모듈 독스트링이 스스로 적어두듯, 같은 규칙이 SQL(사전 필터링) ·{" "}
          <code>core/access/visibility.py</code>(재검증) · <code>frontend/lib/visibility.ts</code>
          (화면 설명) 세 계층에 의도적으로 산다 — 각자 다른 일을 하기 때문입니다. 문제가 되는 것은 같은
          계층 안에서 사본이 늘어나는 것입니다.
        </p>
      </EvidencePanel>
    </div>
  );
}
