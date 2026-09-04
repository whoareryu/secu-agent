import { cookies } from "next/headers";
import { VISITOR_COOKIE } from "@/lib/visitor";

// 감사 로그 · 위반 알림 BFF. 백엔드의 GET /access-log 와
// GET /access-log/violations 를 한 파일로 중계한다(?violations=1 로 분기).
// 방문자 id 를 넘겨 백엔드가 "이 브라우저가 보낸 질의"의 원문만 풀게 한다 —
// 그 외 열람 권한은 여전히 페르소나의 등급·부서가 정한다.
export async function GET(req: Request) {
  const url = new URL(req.url);
  const limit = url.searchParams.get("limit");
  const violations = url.searchParams.get("violations") === "1";
  const path = violations ? "/access-log/violations" : "/access-log";

  const jar = await cookies();
  const 방문자 = jar.get(VISITOR_COOKIE)?.value ?? "";
  const qs = new URLSearchParams();
  if (limit) qs.set("limit", limit);
  if (violations) qs.set("violations", "1");
  if (방문자) qs.set("session_id", 방문자);

  const upstream = await fetch(`${process.env.BACKEND_URL}${path}?${qs}`, {
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
