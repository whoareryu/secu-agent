// /logs 화면의 데이터 통로. 세션 검사가 있었는데 걷었다 — 그 화면을 여는
// 조건이 로그인에서 페르소나의 역할로 바뀌었으므로(스펙 §2.2), 여기 로그인
// 검사가 남아 있으면 감사 페르소나로 들어온 방문자에게 화면은 열리고 표만
// 영영 401 이 된다. /api/access-log 가 같은 이유로 먼저 걷었다.
//
// 가릴 것이 없다는 점도 같이 본다: log_events 는 합성 syslog 라 방문자별로
// 감출 원문이 없다(access-log 의 query 와 다르다).
export async function GET(req: Request) {
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
