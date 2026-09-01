"""공유 시크릿 검사.

브라우저는 이 백엔드를 직접 부르지 않는다. Vercel 의 Route Handler 가
세션을 확인한 뒤 이 시크릿을 달고 부른다.

hmac.compare_digest 를 쓴다. == 로 비교하면 첫 불일치 지점에서 빠져나가
응답 시간이 일치한 글자 수에 따라 달라지고, 그것으로 시크릿을 한 글자씩
알아낼 수 있다.
"""

import hmac
import os

from fastapi import Header, HTTPException

_설정_없음 = "서버 설정 오류"
_거부 = "인증되지 않았다"
_비ascii = "서버 설정 오류: 시크릿이 ASCII 가 아니다"


def 시크릿_검사(x_backend_secret: str | None = Header(default=None)) -> None:
    기대값 = os.environ.get("BACKEND_SHARED_SECRET", "")
    if not 기대값:
        # 닫히는 쪽으로 실패한다. 설정 누락이 '아무나 통과' 가 되면 안 된다.
        raise HTTPException(status_code=500, detail=_설정_없음)
    if not 기대값.isascii():
        # compare_digest 는 양쪽이 같은 비ASCII 문자열이어도 TypeError 로 죽는다.
        # 게다가 클라이언트는 애초에 비ASCII 를 HTTP 헤더 값으로 보내지 못한다 —
        # 양쪽 어디서도 원인을 말해주지 않으므로 여기서 설정 오류라고 밝힌다.
        raise HTTPException(status_code=500, detail=_비ascii)
    if x_backend_secret is None or not hmac.compare_digest(x_backend_secret, 기대값):
        # 없는 것과 틀린 것을 구분해 알려줄 이유가 없다.
        raise HTTPException(status_code=401, detail=_거부)
