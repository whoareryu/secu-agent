# frontend

Next.js 16 App Router · React 19 · TypeScript. 허브·설명·직원·관리자 화면을
로그인 없이 제공하고, 구글 로그인은 `/ask` 의 제출에만 겁니다. `backend/api` 를 라우트 핸들러(BFF)로 감싸
소비하며, 공유 시크릿은 서버에서만 읽습니다.

```bash
npm ci
cp .env.example .env.local    # AUTH_* · BACKEND_URL · BACKEND_SHARED_SECRET
npm run dev                   # http://localhost:3000
```

`BACKEND_URL` 은 백엔드가 실제로 떠 있는 포트를 가리켜야 합니다 — 루트
`docker-compose.yml` 기본값은 8080 이고, 로컬에서 옮겼다면 그 포트입니다.

## 화면

누구나 **허브**(`/`)로 옵니다. 여기서 직원 한 명을 고르면 그 사람이 되어
직원 면을 쓰고, 아래 링크로 설명 면에 들어갑니다.

```
허브      /                             누구나
설명 면   /how · /principals · /documents   누구나
직원 면   /ask · /my/documents          페르소나 쿠키 필요
관리자 면 /admin · /logs                 페르소나의 역할이 감사인 경우만
```

로그인은 권한이 아니라 요금 게이트입니다 — `/ask` 뒤에 유료 LLM 이 있어
그 제출에만 걸립니다.

페르소나 쿠키에는 **이름만** 담깁니다. 등급·부서·역할은 백엔드가
`principals` 테이블에서 번역합니다 — 클라이언트가 권한 값을 실어 보낼 수
있으면 그것이 곧 사칭 경로이기 때문입니다.

## 검사

```bash
npm test          # lib/ 순수 함수 (node --test)
npx tsc --noEmit
npm run build
```

`lib/` 에만 테스트가 있습니다. 컴포넌트와 라우트 핸들러는 아직 없습니다 —
그중 가장 위험한 자리는 `lib/surface.ts` 의 `guard()` 이고, 그것은 순수
함수라 `lib/surface.test.ts` 가 덮습니다.
