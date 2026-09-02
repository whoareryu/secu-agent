import { auth } from "@/auth";
import { roleFor } from "@/lib/session";

// 관리자 전용 데이터이므로 로그인만으로는 부족하다 — /api/access-log 와
// 같은 이유, 같은 모양이다(사이드바가 감추는 것은 프레젠테이션일 뿐이라
// 서버가 role 을 다시 확인한다).
export async function GET(req: Request) {
  const session = await auth();
  if (!session?.user?.email) {
    return Response.json({ error: "로그인이 필요합니다" }, { status: 401 });
  }
  if (roleFor(session.user.email) !== "admin") {
    return Response.json({ error: "권한이 없습니다" }, { status: 403 });
  }
  const persona = new URL(req.url).searchParams.get("persona") ?? "";
  const upstream = await fetch(
    `${process.env.BACKEND_URL}/log-events?persona=${encodeURIComponent(persona)}&limit=100`,
    { headers: { "X-Backend-Secret": process.env.BACKEND_SHARED_SECRET ?? "" } }
  );
  if (!upstream.ok) {
    return Response.json({ error: "백엔드 오류", status: upstream.status }, { status: upstream.status });
  }
  return Response.json(await upstream.json());
}
