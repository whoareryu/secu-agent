// 사이드바의 GET /healthz 블록이 부르는 BFF. 백엔드 /healthz 는 시크릿이
// 필요 없지만, 브라우저가 백엔드 주소를 알지 못하도록 여기서 중계한다.
//
// 세션 검사가 있었는데 걷었다 — 이 readout 을 켜는 것은 설명 면이고(SurfaceNav
// 의 healthz), 그 면은 로그인 없이 열린다(스펙 §2.2). 이 배포가 상시 가동이
// 아니라서 "백엔드가 꺼져 있다" 를 미리 알려주는 것이 이 블록의 존재 이유인데,
// 검사가 남으면 비로그인 방문자에게는 그 신호가 401 로만 온다.
export async function GET() {
  const upstream = await fetch(`${process.env.BACKEND_URL}/healthz`);

  if (!upstream.ok) {
    return Response.json(
      { error: "백엔드 오류", status: upstream.status },
      { status: upstream.status }
    );
  }
  return Response.json(await upstream.json());
}
