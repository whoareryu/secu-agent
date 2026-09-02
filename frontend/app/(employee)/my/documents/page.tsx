import { cookies } from "next/headers";
import Blueprint from "@/components/Blueprint";
import { visible, type Document } from "@/lib/visibility";
import { PERSONA_COOKIE, personaFrom } from "@/lib/persona";
import type { Principal } from "@/components/PersonaSegment";

async function 백엔드<T>(path: string): Promise<T> {
  const r = await fetch(`${process.env.BACKEND_URL}${path}`, {
    headers: { "X-Backend-Secret": process.env.BACKEND_SHARED_SECRET ?? "" },
    cache: "no-store",
  });
  if (!r.ok) throw new Error(`${path} ${r.status}`);
  return r.json();
}

// GET /documents 는 권한 필터 없이 전부 돌려준다(그 엔드포인트의 독스트링
// 참고 — 검색 경로가 아니라 카탈로그다). 이 화면은 **서버에서** 걸러 그린다.
// 클라이언트로 전부 내려보내고 화면에서 숨기면, 못 보는 문서의 제목이
// 브라우저에 도착한다 — 제목만으로 존재가 드러난다는 것이 이 프로젝트가
// access_records 에서 제목을 뺀 이유다.
export default async function MyDocumentsPage() {
  const jar = await cookies();
  const name = jar.get(PERSONA_COOKIE)?.value;

  // 이 배포는 상시 가동이 아니다(app/page.tsx 의 같은 처리 참조) — 백엔드를
  // 켜 둔 맥이 꺼져 있으면 백엔드() 가 던진다. 셸이 이미 principals() 로
  // 백엔드 생존을 확인했더라도, 그 사이 꺼졌을 수 있으니 이 화면도 같은
  // 모양으로 잡는다.
  let 문서: Document[];
  let 계정: Principal[];
  try {
    [문서, 계정] = await Promise.all([
      백엔드<Document[]>("/documents"),
      백엔드<Principal[]>("/principals"),
    ]);
  } catch {
    return (
      <Blueprint className="card" style={{ padding: 24, gap: 14, borderColor: "var(--color-accent-700)", maxWidth: 900 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span className="tag tag-outline">502</span>
          <span style={{ fontFamily: "var(--font-heading)", fontSize: 22 }}>백엔드에 닿지 못했습니다</span>
        </div>
        <p style={{ margin: 0, fontSize: 14, lineHeight: 1.65, color: "var(--color-neutral-700)" }}>
          이 배포는 상시 가동이 아니라 필요할 때만 백엔드를 켜 둡니다. 지금
          꺼져 있어 열람 가능한 문서를 가져오지 못했습니다 — 켜지기 전에는
          새로고침해도 같은 결과입니다.
        </p>
      </Blueprint>
    );
  }

  // 쿠키 원값을 그대로 find 에 넣지 않는다. 부모 레이아웃이 같은 판정을 이미
  // 하지만 그것에 기대지 않는다 — App Router 에서 레이아웃과 페이지는 별개
  // 세그먼트라 이 함수가 레이아웃의 redirect() 보다 먼저 돌 수 있고, 그러면
  // find 가 undefined 를 주어 아래 me.department 가 TypeError 로 500 을 낸다.
  // 낡은 쿠키(principals 에서 사라진 페르소나)나 편집된 쿠키에서 실제로 난다.
  // layout.tsx 의 같은 모양은 바로 윗줄의 redirect() 가 같은 함수 안에서
  // 던지므로 진짜로 도달 불가라 완화 근거가 되지 않는다.
  const 이름 = personaFrom(name, 계정.map((p) => p.name));
  const me = 이름 === null ? undefined : 계정.find((p) => p.name === 이름);
  if (me === undefined) {
    return (
      <Blueprint className="card" style={{ padding: 24, gap: 14, borderColor: "var(--color-accent-700)", maxWidth: 900 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span className="tag tag-outline">계정 미확인</span>
          <span style={{ fontFamily: "var(--font-heading)", fontSize: 22 }}>직원을 다시 골라 주세요</span>
        </div>
        <p style={{ margin: 0, fontSize: 14, lineHeight: 1.65, color: "var(--color-neutral-700)" }}>
          어느 계정으로 보는 중인지 확인하지 못했습니다. 누구의 권한으로 걸러야 할지
          알 수 없어 목록을 만들지 않았습니다 — <a href="/">허브</a>에서 직원을 고르면 이어집니다.
        </p>
      </Blueprint>
    );
  }
  const 보이는것 = 문서.filter((d) => visible(d, me));

  return (
    <div style={{ maxWidth: 1000, display: "flex", flexDirection: "column", gap: 18 }}>
      <p style={{ margin: 0, fontSize: 13.5, lineHeight: 1.7, color: "var(--color-neutral-700)" }}>
        {me.department} · 등급 {me.clearance} 로 열람 가능한 문서 {보이는것.length}건입니다.
        이 목록은 계정의 부서와 등급으로 결정됩니다.
      </p>
      <p style={{ margin: 0, fontSize: 12.5, lineHeight: 1.65, color: "var(--color-neutral-700)" }}>
        걸러내기는 서버에서 끝납니다 — 목록에 없는 문서는 제목조차 브라우저에 오지 않습니다.
        다만 이 목록을 고른 것은 <code>lib/visibility.ts</code> 이고, 그것은
        SQL(<code>permission_sql.권한_WHERE</code>) · 파이썬(<code>core/access/visibility.py</code>)에
        이은 세 번째 사본입니다. 질의가 근거 조항을 고를 때 실제로 거는 것은 그 SQL 이지 이 사본이
        아닙니다 — 둘이 어긋나면 어긋나는 쪽은 답이 아니라 이 목록입니다.
      </p>
      {보이는것.map((d) => (
        <Blueprint key={d.id} className="card" style={{ padding: 16 }}>
          <div style={{ fontSize: 15, fontFamily: "var(--font-heading)" }}>{d.title}</div>
          <div style={{ fontSize: 12, color: "var(--color-neutral-700)", marginTop: 4 }}>
            {d.doc_type} · 조각 {d.chunk_count}개 · 요구 등급 {d.required_clearance}
            {d.allowed_departments.length > 0 && ` · ${d.allowed_departments.join(", ")} 전용`}
          </div>
        </Blueprint>
      ))}
    </div>
  );
}
