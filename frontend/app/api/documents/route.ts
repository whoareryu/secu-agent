// 문서 화면이 부르는 BFF. 백엔드 /documents 는 권한 필터 없이 전부 돌려준다
// (이 화면 자체가 "규칙이 어떻게 적용되는지"를 보여주는 자리라서). 백엔드
// 주소도 공유 시크릿도 브라우저에 내려가지 않는다.
//
// 세션 검사가 있었는데 걷었다 — /documents 는 설명 면이고 설명 면은 로그인을
// 요구하지 않는다(스펙 §2.2). 여기 목록은 원래부터 권한 필터를 타지 않으므로
// 로그인이 가리던 것도 없었다. 무엇이 누구에게 보이는지는 이 표가 설명하는
// 대상이지 이 표가 감추는 대상이 아니다.
export async function GET() {
  const upstream = await fetch(`${process.env.BACKEND_URL}/documents`, {
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
