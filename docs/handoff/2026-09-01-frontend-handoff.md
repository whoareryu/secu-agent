# Handoff: Secu-Agent 프론트엔드 (권한 인식 규정 검색 + 관리자 대시보드)

## Overview
사내 보안 규정 RAG 에이전트 `secu-agent` 의 웹 프론트엔드입니다. 직원은 규정을 자연어로 질의하고, 답변과 근거 조항을 받습니다. 권한(부서 · 등급)에 따라 검색 결과가 달라지며, 권한 밖 문서의 **존재 자체가 결과 개수에도 순위에도 드러나지 않는 것**이 이 제품의 핵심입니다. 관리자 세션은 직원별 서류 열람 이력과 권한 밖 열람 알림을 보고, 이상이 있으면 secu-agent 담당자에게 문의합니다.

백엔드는 이미 존재합니다(`backend/`: FastAPI + LangGraph + pgvector). 이 핸드오프는 아직 착수 전인 `frontend/`(Next.js App Router · TypeScript) 구현을 위한 것입니다.

## About the Design Files
이 번들의 `Secu-Agent Dashboard.dc.html` 는 **HTML 로 만든 디자인 레퍼런스**입니다. 의도한 화면과 동작을 보여주는 프로토타입이며, 그대로 복사해 쓰는 프로덕션 코드가 아닙니다. 대상 코드베이스(`frontend/`, Next.js App Router + TypeScript, Auth.js)의 기존 패턴과 라이브러리로 **재구현**하는 것이 과제입니다. 스타일은 Industry 디자인 시스템(`_ds/industry-.../styles.css`)의 클래스와 토큰을 그대로 옮기면 됩니다 — 이 스타일시트는 번들에 포함되어 있습니다.

## Fidelity
**High-fidelity.** 최종 색·타이포·간격·상호작용까지 확정된 목업입니다. 픽셀 단위로 재현하되, 값은 하드코딩하지 말고 `styles.css` 의 CSS 변수(`var(--color-*)`, `var(--font-*)`, `var(--space-*)`)를 사용하세요.

## Screens / Views

### 1. 로그인 / Sign in
- **Purpose**: 구글 OAuth 로그인. 계정 유형(일반 사용자 / 관리자) 선택.
- **Layout**: 뷰포트 전체 `display:grid; place-items:center`, 폭 420px 컬럼, `gap:28px`.
- **Components**
  - 워드마크 `Secu-Agent` — 13px, `letter-spacing:.34em`, uppercase, `var(--color-accent)`
  - 제목 38px / line-height 1.05, 부제 22px `var(--color-neutral-600)`
  - 카드: `.card.blueprint` + 코너 마크 4개, `padding:28px; gap:18px`
  - 안내문 14px / 1.55 `var(--color-neutral-700)`
  - Role 선택: 1px `var(--color-divider)` 테두리 안에 2개 버튼(flex:1). 선택 시 `background:var(--color-accent); color:var(--color-bg)`
  - 기본 버튼: `.btn.btn-primary.blueprint`, height 44px, 텍스트 "Google 계정으로 로그인 / Continue with Google"
  - 하단 고지(spec §3.2 요구, 삭제 금지): "인증은 실제 구글 OAuth 입니다. 부서·등급은 시연을 위해 선택하는 값이며, **선택된 값이 실제 권한 필터를 그대로 탑니다.**"
  - 푸터 행: Vercel · BFF / Cloudflare Container / Neon · pgvector — 11px uppercase, 사이에 1px 구분선

### 2. 앱 셸 / App shell
- **Layout**: `display:grid; grid-template-columns:236px 1fr; min-height:100vh`
- **사이드바**: `background:var(--color-accent-900)`, 글자 `#e9eef3`. 브랜드 19px `letter-spacing:.28em`. 메뉴 항목은 한국어 14px + 영문 10.5px uppercase(opacity .55), 우측에 배지. 활성 항목: `background:rgba(255,255,255,.09)`, `border-left:3px solid var(--color-accent-300)`, 글자 흰색. hover: `rgba(255,255,255,.07)`. 하단에 `GET /healthz` 블록(db true · model ready · status ok).
- **메뉴**: 질의(Ask, 배지 `/ask`) · 문서 · 권한(Documents) · 계정(Principals) · 감사 로그(Audit log, 배지 W4) · **관리자 대시보드(Admin, 배지 ADMIN — 관리자 세션에서만 렌더)**
- **헤더**: `padding:26px 40px 18px`, 하단 1px 구분선. 좌측 영문 kicker 10.5px `letter-spacing:.18em` + 한글 제목 30px. 우측 계정 이메일 13px + 세션 설명 11px + `.btn.btn-secondary` 로그아웃.
- **본문**: `padding:28px 40px 56px`

### 3. 질의 / Ask (기본 화면)
- **Layout**: `grid-template-columns:minmax(0,1fr) 320px; gap:32px; max-width:1240px; align-items:start`
- **질의 카드**(`.card.blueprint`, padding 22px): kicker "Persona · 시연 계정" + 우측 "POST /ask · persona 이름만 전송". 페르소나 3분할 세그먼트(김개발 · 개발팀 등급 1 / 박인사 · 인사팀 등급 2 / 최임원 · 경영지원팀 등급 3), 선택 시 accent 채움. 입력 `.input`(height 42px) + `.btn.btn-primary`(height 42px, min-width 104px, 라벨 "질의 / Ask", 로딩 중 "질의 중…" + disabled).
- **로딩 상태**: kicker "Running", 폭 62% / 88% / 40% 회색 바 3개가 `sa-pulse 1.1s` 로 깜빡임(각 0 / .15s / .3s 지연). 설명: 스트리밍하지 않고 완성된 응답을 한 번에 받음.
- **에러 상태**: 테두리 `var(--color-accent-700)`, `.tag.tag-outline` 502 + "백엔드에 닿지 못했습니다 / Upstream unavailable", 설명(예외 본문에 chunk_id 외 정보를 싣지 않는다), 재시도 버튼.
- **답변 카드**: 태그 행(페르소나 이름 `.tag-accent`, 부서 · 등급 `.tag-neutral`) + 우측 메타 "tool_calls N · hits N · NNNms". kicker "Answer", 본문 15.5px / line-height 1.72 / `text-wrap:pretty`.
- **근거 조항**: 제목 20px "근거 조항 / Cited clauses" + 설명 "hits[] · 순서가 곧 순위입니다 (RRF 점수는 노출하지 않습니다)". `grid-template-columns:repeat(auto-fill,minmax(280px,1fr)); gap:18px`. 카드마다 순위 kicker(#1…), `.tag.tag-outline` 조항 코드, `.card-title` 문서명, 본문 발췌, `.card-meta` chunk_id.
- **사전 필터링 설명 카드**: `background:var(--color-accent-100)`, 본문 `var(--color-accent-900)` — "숨겨진 문서는 결과 개수에도 순위의 빈자리에도 드러나지 않습니다."
- **우측 레일**: ① "같은 질문 · 세 계정" 카드 — 페르소나별 결과 요약 행(예: "5건 · 6.1.x 포함" / "5건 · ISMS-P 로 채워짐") ② "예시 질의" 카드 — 클릭 시 입력창에 채워짐.

### 4. 문서 · 권한 / Documents
- 상단: 안내문 + 페르소나 칩 3개 + 우측 `.tag.tag-neutral` "코퍼스 338 청크 / 338 chunks"
- `.table`: 문서 / 유형 / 필요 등급 / 허용 부서 / source_path / 가시성. 가시성은 현재 페르소나 기준으로 `clearance <= p.clearance && (depts.length === 0 || depts.includes(p.dept))` 를 계산 — 보임(accent 실선 배지) / 가려짐(neutral 점선 배지).
- 하단 주석: 허용 부서가 비어 있으면 전사 공개. ISMS-P 는 본문이 실제 공개 표준이고 권한 등급만 부여, 사내 규정과 시연 계정은 합성.

### 5. 계정 / Principals
- `.table`: 이름 / 부서 / 등급 / 직급 / 현재 선택
- 카드 2개: seed 명령(`python -m pipeline.cli seed-principals`), "사칭 경로가 없는 이유"(AskRequest 에 department·clearance 가 없다 · 없는 이름에는 "알 수 없는 페르소나"만 반환)

### 6. 감사 로그 / Audit log (W4 계획)
- `.tag.tag-outline` "W4 계획 / Planned" + 설명
- 비활성 필터 행(opacity .5, pointer-events none)
- 빈 상태 테이블(ts / host / process / event_type / principal_name / severity / raw), 56px 상하 여백의 안내
- `log_events` 스키마 요약 카드(모노스페이스)

### 7. 관리자 대시보드 / Admin (관리자 전용)
- 상단: `.tag.tag-outline` "Admin only" + "열람 이력과 권한 이상 알림은 관리자 세션에서만 보입니다."
- **요약 4칸**(`repeat(4,1fr); gap:18px`): 이번 주 질의 342 / 열람된 서류 128 / 차단된 요청 17 / 확인 필요 알림 N. 숫자는 44px Barlow Condensed. 확인 필요 알림이 0보다 크면 카드에 `border-color:var(--color-accent-700); background:var(--color-accent-100)`.
- **권한 밖 열람 알림**: 테두리 `var(--color-accent-700)`. 테이블 — 발생 시각 / 직원(+부서 · 등급) / 대상(chunk 식별자) / 사유 / 처리(미확인은 `background:var(--color-accent-200)`, 확인 완료는 neutral 점선). 주석: 알림에는 식별자만 담고 문서 본문·제목은 담지 않는다.
- **직원별 서류 열람 이력**: 필터 칩(전체 / 차단만 / 김개발 / 박인사 / 최임원). 테이블 — 시각 / 직원 / 부서 · 등급 / 질의 / 열람 문서 / 조항(`.tag-neutral`) / 결과(정상 열람 · 차단). 하단 "표시 N건 · 전체 N건".
- **문의 카드**: `background:var(--color-accent-100)`, 우측에 `.btn.btn-primary.blueprint` "담당자에게 문의 / Contact". 전송 후 접수 문구(티켓 번호 · 담당 메일) 노출.
- **문의 다이얼로그**: `.dialog-backdrop`(`position:fixed; inset:0; background:rgba(29,45,61,.45); z-index:50`) + `.dialog.blueprint`(520px, padding 26px, `background:var(--color-bg)`). 문의 유형 세그먼트(권한 밖 문서 열람 / 열람 이력 오류 / 권한 설정 변경 요청 / 기타 — 마지막 항목은 `border-right:0`), 내용 textarea, 고지("미확인 알림 N건과 관련 열람 이력, 관리자 계정 정보가 함께 전송됩니다. 문서 본문은 첨부되지 않습니다."), 취소 / 문의 보내기.

## Interactions & Behavior
- **로그인**: Role 선택 → 로그인 → 앱 셸(질의 화면). 로그아웃 시 로그인 화면 복귀. 관리자 메뉴는 `role === "admin"` 일 때만 **렌더 자체를 하지 않음**(숨김이 아니라 미포함).
- **질의**: 제출 → `loading` → 성공 `done` / 실패 `error`. 프로토타입은 setTimeout(기본 1200ms)로 흉내 냈습니다. 실제 구현은 `POST /api/ask` (Next.js Route Handler)가 Auth.js 세션을 확인한 뒤 공유 시크릿 헤더로 백엔드 `POST /ask` 를 호출합니다. **스트리밍하지 않습니다.**
- **페르소나 전환**: 즉시 결과 세트 교체. 같은 질의에서 세 계정의 hits 개수는 항상 동일해야 합니다 — 이것이 제품 주장의 핵심이므로 UI 가 개수 차이를 만들면 안 됩니다.
- **예시 질의 클릭**: 입력창 값 교체.
- **문서 가시성**: 페르소나 칩 변경 시 즉시 재계산.
- **열람 이력 필터**: 클라이언트 필터. 행 수 표시 갱신.
- **문의**: 열기 → 유형 선택 → 내용 입력 → 전송 → 다이얼로그 닫힘 + 접수 배너.
- **hover/active/focus**: Industry 스타일시트가 이미 정의합니다(accent 램프 한 단계, `:focus-visible` 2px accent 링). 페이지에서 재정의하지 마세요.
- **반응형**: 데스크톱 전용 목업입니다(1240px 기준). 태블릿 이하 대응은 별도 정의 필요.

## State Management
```ts
signedIn: boolean
role: "member" | "admin"
screen: "ask" | "docs" | "principals" | "logs" | "admin"
persona: "김개발" | "박인사" | "최임원"
query: string
status: "idle" | "loading" | "done" | "error"
logFilter: "전체" | "차단만" | 직원명
inquiryOpen: boolean; inquirySent: boolean; inquiryTopic: string; inquiryText: string
```
데이터 요구:
- `POST /ask` → `{ answer, hits: [{ chunk_id, clause_code, doc_title, text }], persona: { name, department, clearance }, tool_calls }` (`backend/api/schemas.py`)
- **요청에 department·clearance 를 절대 싣지 마세요.** persona 이름만 보내고 서버가 principals 테이블에서 번역합니다 — 클라이언트가 등급을 보낼 수 있으면 그것이 곧 사칭 경로입니다.
- `GET /healthz` → `{ status, db, model }`
- 문서 목록 · 열람 이력 · 권한 알림 엔드포인트는 아직 없습니다. 프로토타입은 목 데이터로 그렸고, 열람 이력/알림은 `log_events` 테이블(W4)이 채워진 뒤 붙일 자리입니다.

## Design Tokens
모두 `styles.css` 에 있습니다. 하드코딩 금지.
- 배경 `--color-bg` #f2f2f3 · 텍스트 `--color-text` #1d1f20 · 강조 `--color-accent` #5980a6
- accent 램프 100 #eef6ff · 200 #d6ebff · 300 #b5d9fd · 600 #597ea3 · 700 #416180 · 800 #2c455d · 900 #1d2d3d (사이드바 필드)
- neutral 램프 300 #d4d4d7 · 400 #b7b7ba · 500 #98989b · 600 #7a7a7d · 700 #5d5d60
- 구분선 `--color-divider` = `color-mix(in srgb, #1d1f20 16%, transparent)`
- 타이포 `--font-heading` Barlow Condensed 600 / `--font-body` Barlow
- 간격 `--space-1..8` 3.4 / 6.8 / 10.2 / 13.6 / 20.4 / 27.2px
- 라운드: 카드 · 버튼 · 입력 · 태그는 **0** (Industry 는 사각 와이어프레임)
- 프레임: `.blueprint` + `<i class="corner tl|tr|bl|br">` 4개 — 카드 · 도형 · 기본 버튼에서 절대 빼지 마세요.

## Assets
- 아이콘 없음. 아이콘을 추가한다면 Lucide, stroke-width 1.5.
- 이미지 없음.
- 폰트: Barlow / Barlow Condensed (Industry 스타일시트가 로드).

## Files
- `Secu-Agent Dashboard.dc.html` — 전체 프로토타입(6개 화면 + 로그인). 템플릿은 `<x-dc>` 안, 상태·목 데이터는 하단 `<script data-dc-script>` 의 `class Component` 에 있습니다. 목 데이터(RESULTS · DOCS · ALERTS · ACCESS_LOG · PERSONAS)는 그 스크립트 상단 상수에 모여 있습니다.
- `styles.css` — Industry 디자인 시스템 스타일시트(토큰 + 컴포넌트). HTML 이 `_ds/industry-.../styles.css` 경로로 참조하므로, 열어볼 때는 경로를 맞추거나 링크를 수정하세요.
- `support.js` — 프로토타입 런타임. 구현에는 필요 없습니다.

## 참고 (백엔드 계약)
- 권한 규칙: `backend/core/access/visibility.py`
- 도구 출력 재검증: `backend/core/agent/policy.py` (위반 시 `AccessViolation`, 메시지에 chunk_id 만 담음 — UI 도 같은 원칙을 지킬 것)
- HTTP 타입: `backend/api/schemas.py` · 앱: `backend/api/main.py`
- 배포: Vercel(Next.js · BFF) → Cloudflare Container(FastAPI) → Neon(pgvector). 브라우저는 백엔드 주소도 공유 시크릿도 받지 않습니다.
