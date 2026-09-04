# frontend

Next.js 16 App Router · React 19 · TypeScript. 구글 로그인 뒤에서 `/ask` 와
설명·관리자 화면을 제공합니다. `backend/api` 를 라우트 핸들러(BFF)로 감싸
소비하며, 공유 시크릿은 서버에서만 읽습니다.

```bash
npm ci
cp .env.example .env.local    # AUTH_* · BACKEND_URL · BACKEND_SHARED_SECRET · ADMIN_EMAILS
npm run dev                   # http://localhost:3000
```

`BACKEND_URL` 은 백엔드가 실제로 떠 있는 포트를 가리켜야 합니다 — 루트
`docker-compose.yml` 기본값은 8080 이고, 로컬에서 옮겼다면 그 포트입니다.

## 화면

로그인하면 **허브**(`/`)로 옵니다. 여기서 직원 한 명을 고르면 그 사람이 되어
직원 면을 쓰고, 아래 링크로 설명 면에 들어갑니다.

```
직원 면   /ask · /my/documents          페르소나 쿠키 필요
설명 면   /how · /principals · /documents   로그인만 하면 누구나
관리자 면 /admin · /logs                 ADMIN_EMAILS 에 있는 계정만
```

페르소나 쿠키에는 **이름만** 담깁니다. 등급·부서는 백엔드가 `principals`
테이블에서 번역합니다 — 클라이언트가 권한 값을 실어 보낼 수 있으면 그것이
곧 사칭 경로이기 때문입니다.

## 검사

```bash
npm test          # lib/ 순수 함수 (node --test)
npx tsc --noEmit
npm run build
```

`lib/` 에만 테스트가 있습니다. 컴포넌트와 라우트 핸들러는 아직 없습니다 —
그중 가장 위험한 자리는 `app/api/access-log/route.ts` 와
`app/api/log-events/route.ts` 의 관리자 검사입니다. 백엔드가 아니라 여기가
유일한 강제 지점입니다.
