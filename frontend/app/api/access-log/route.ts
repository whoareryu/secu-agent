import { auth } from "@/auth";
import { roleFor } from "@/lib/session";

// 감사 로그 · 위반 알림 BFF. 백엔드의 GET /access-log 와
// GET /access-log/violations 를 한 파일로 중계한다(?violations=1 로 분기).
// 관리자 대시보드 전용 데이터이므로 로그인만으로는 부족하다 — role === "admin"
// 이어야 한다. 사이드바가 관리자 메뉴를 숨기는 것은 프레젠테이션일 뿐이라
// 서버가 다시 확인한다(콘솔에서 누구나 이 경로를 fetch 할 수 있다).
export async function GET(req: Request) {
  const session = await auth();
  if (!session?.user?.email) {
    return Response.json({ error: "로그인이 필요합니다" }, { status: 401 });
  }
  if (roleFor(session.user.email) !== "admin") {
    return Response.json({ error: "권한이 없습니다" }, { status: 403 });
  }

  const url = new URL(req.url);
  const limit = url.searchParams.get("limit");
  const violations = url.searchParams.get("violations") === "1";
  const path = violations ? "/access-log/violations" : "/access-log";
  const qs = limit ? `?limit=${encodeURIComponent(limit)}` : "";

  const upstream = await fetch(`${process.env.BACKEND_URL}${path}${qs}`, {
    headers: { "X-Backend-Secret": process.env.BACKEND_SHARED_SECRET ?? "" },
  });

  if (!upstream.ok) {
    return Response.json(
      { error: "백엔드 오류", status: upstream.status },
      { status: upstream.status }
    );
  }
  return Response.json(await upstream.json());
}
