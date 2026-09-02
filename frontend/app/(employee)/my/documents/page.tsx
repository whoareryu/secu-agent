import { cookies } from "next/headers";
import Blueprint from "@/components/Blueprint";
import { visible, type Document } from "@/lib/visibility";
import { PERSONA_COOKIE } from "@/lib/persona";
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

  const me = 계정.find((p) => p.name === name)!;
  const 보이는것 = 문서.filter((d) => visible(d, me));

  return (
    <div style={{ maxWidth: 1000, display: "flex", flexDirection: "column", gap: 18 }}>
      <p style={{ margin: 0, fontSize: 13.5, lineHeight: 1.7, color: "var(--color-neutral-700)" }}>
        {me.department} · 등급 {me.clearance} 로 열람 가능한 문서 {보이는것.length}건입니다.
        다른 계정으로 들어오면 이 목록의 길이가 달라집니다.
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
