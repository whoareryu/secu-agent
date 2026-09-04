// 계정 목록을 부르는 BFF. 페르소나를 하드코딩하지 않기 위해 백엔드
// principals 테이블을 그대로 중계한다. 백엔드 주소도 공유 시크릿도
// 브라우저에 내려가지 않는다.
//
// 세션 검사가 있었는데 걷었다 — 이 목록에 기대는 화면(설명 면의 계정·문서,
// 관리자 면의 로그)이 이제 로그인 없이 열리므로(스펙 §2.2), 검사가 남으면
// 화면만 열리고 표는 영영 401 이 된다. 로그인은 애초에 인가 경계가 아니었다:
// 구글 계정이면 누구나 통과했고, 유일한 인가 용도이던 ADMIN_EMAILS 는
// §2.5 가 없앴다.
export async function GET() {
  const upstream = await fetch(`${process.env.BACKEND_URL}/principals`, {
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
