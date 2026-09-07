# k3s · Colima 배포 설계 — 온프레미스

- **작성일**: 2026-09-07
- **상태**: 확정
- **대체하는 것**: `docs/superpowers/plans/2026-09-02-w5-deploy.md` 의 배포 토폴로지
- **상위 문서**: `docs/superpowers/specs/2026-09-01-w3-deployment-design.md` §2

---

## 1. 이 문서의 범위

배포 토폴로지 하나만 정한다. 도메인·검색·권한 필터링·인증·HTTP 표면·UI 는
상위 문서들이 정한 그대로다. **백엔드 코드는 한 줄도 바뀌지 않는다** — 이
설계가 성립하는지의 시험 중 하나가 그것이다.

W5 는 백엔드와 DB 를 이 맥의 docker compose 에 두고 Cloudflare Tunnel 로
공개했다. 이 문서는 **백엔드와 터널만** k3s 로 옮긴다. DB 는 움직이지 않는다.

## 2. 토폴로지

```
브라우저 ──HTTPS──> Vercel (Next.js · Auth.js)          [변경 없음]
                       │ HTTPS + 공유 시크릿 헤더
                       ▼
              Cloudflare — secu-agent 전용 터널          [신규]
┌───────────────────────────────────────────────────────┐
│ Colima VM (4 CPU · 8GiB) · k3s 단일 노드               │
│                                                       │
│   cloudflared ──ClusterIP──> secu-backend:8080        │
│                                    │                  │
└────────────────────────────────────┼──────────────────┘
                                     │ psycopg → 192.168.5.2:5433
                    Docker Desktop: pgvector      [변경 없음]
                      volume secuagent_pgdata
                                     │
                          Gemini (Vertex) — 아웃바운드
```

## 3. 결정과 그 대가

### 결정 1 — DB 는 클러스터에 들이지 않는다

pgvector 는 Docker Desktop 의 `secuagent_pgdata` 볼륨 위에서 계속 돈다.

W5 결정 1 이 "DB 가 영속이다 · 열람 기록이 살아남는다" 를 이 프로젝트의
자산으로 못박았다. 클러스터로 들이면 그 볼륨을 PV 로 이관해야 하는데,
**슈파베이스로 옮길 계획이 이미 있으므로 그 이관은 버려지는 작업이다.**

얻는 것: 클러스터가 무상태가 된다. PV·StatefulSet·백업 문제가 전부 사라지고,
`colima delete` 가 데이터를 지울 수 없다.

대가: 파드가 VM 경계를 넘어 macOS 호스트에 닿아야 한다. `192.168.5.2` 라는
매직 IP 가 생긴다.

**그 대가를 한 곳에 가둔다.** IP 를 DSN 에 박지 않고 셀렉터 없는 Service
`secu-db` 뒤에 둔다(`deploy/k8s/db-endpoint.yaml`). 백엔드가 아는 것은
`secu-db:5432` 라는 이름뿐이다. 슈파베이스로 옮길 때는 `.env` 에
`SECUAGENT_DSN` 을 적고 그 파일을 지운다 — 매니페스트도 코드도 그대로다.

### 결정 2 — 레지스트리를 쓰지 않는다

`colima start --kubernetes` 는 기본 docker 런타임으로 k3s 를 띄우고, k3s 는
같은 VM 의 그 도커 데몬을 CRI 로 쓴다. `docker context use colima` 후 빌드한
이미지를 클러스터가 그대로 본다.

W5 결정 1 이 지킨 "이미지를 레지스트리에 올릴 일이 없다" 가 유지된다.

덧붙여, W3 스펙이 "약 3GB" 라 적은 이미지는 **실측 1.0GB** 다. CPU 전용
torch 를 쓰는 지금 Dockerfile 기준이다.

대가: 이미지 태그가 로컬에만 존재하므로 `imagePullPolicy: Never` 가 필수다.
빠뜨리면 쿠버네티스가 Docker Hub 에서 `secu-backend` 를 찾다가 `ErrImagePull`
로 죽는다.

### 결정 3 — 전용 터널을 새로 만든다

기존 `whoareryu-cloudflared` 를 재사용하지 않는다. 그것은 새싹 스택의 것이고,
공유 브리지에서 이름으로 백엔드를 불렀다. 백엔드가 클러스터로 들어가면 그
이름이 그 네트워크에서 사라진다.

지워진 `docker-compose.tunnel.yml` 은 그 구성의 위험을 스스로 적어 두고
있었다 — 같은 네트워크에 남의 redis·pgvector·adminer 가 있어 도달성이
양방향이고, 공유 시크릿이 유일한 방어선이며, "전용 네트워크로 분리하는 것이
옳지만 새싹 스택 쪽 설정을 건드려야 해서" 하지 못했다고.

**이 이전이 그 분리를 공짜로 만든다.** 새싹 설정은 건드리지 않았다.

### 결정 4 — 재부팅 자동 기동을 LaunchAgent 로 되산다

compose 의 `restart: unless-stopped` 는 "재부팅 뒤에 사람이 붙어야 살아나면
그건 배포가 아니다" 를 지키려고 있었다. 파드의 restartPolicy 는 VM 이 떠
있을 때만 의미가 있고, **Colima 는 부팅 시 스스로 뜨지 않는다.**

`deploy/com.secuagent.colima.plist` 가 그 빈자리를 메운다. Docker Desktop 은
앱 자체 설정으로 로그인 시 기동한다.

대가: 의존 사슬이 둘이 된다(Colima · Docker Desktop). 어느 하나가 안 뜨면
백엔드가 죽는다. W5 결정 2 가 이미 "24시간 가동하지 않는다, 그 사실을 화면이
말한다" 를 정해 두었으므로 이 대가는 새로 생긴 것이 아니다.

## 4. 구성 요소

| 파일 | 내용 |
|---|---|
| `deploy/k8s/namespace.yaml` | `secu-agent` 네임스페이스 |
| `deploy/k8s/db-endpoint.yaml` | 셀렉터 없는 Service + EndpointSlice → `192.168.5.2:5433` |
| `deploy/k8s/backend.yaml` | Deployment(replicas 1, Recreate) + ClusterIP Service |
| `deploy/k8s/cloudflared.yaml` | Deployment. 토큰 방식이라 설정 파일 없음 |
| `deploy/secret.sh` | `.env` + `gcp-sa.json` → Secret. 값은 커밋되지 않는다 |
| `deploy/com.secuagent.colima.plist` | 로그인 시 Colima 기동 |

### 4.1 probe

compose 의 `start_period: 90s` 는 **`startupProbe` 로** 옮긴다
(`periodSeconds: 10` × `failureThreshold: 12` = 120초).

`livenessProbe.initialDelaySeconds` 로 옮기면 안 된다. compose 주석이 적어 둔
사고 — "기동 중인 컨테이너를 계속 죽이는 루프" — 가 그대로 재현된다.
startupProbe 가 통과하기 전까지 liveness 는 아예 돌지 않는다는 것이 이
설계가 기대는 성질이다.

`readinessProbe` 는 compose 에 없던 것이다. 모델이 로드되는 동안 cloudflared
가 트래픽을 보내지 않게 한다. k3s 로 오면서 실제로 좋아지는 유일한 지점이다.

### 4.2 시크릿이 닫히는 쪽으로 실패하게 하기

compose 는 `${BACKEND_SHARED_SECRET:?...}` 로 설정 누락을 기동 실패로
만들었다. **쿠버네티스에는 그 장치가 없다** — Secret 이 비어도 파드는 뜨고,
그 순간 아는 값으로 열린 백엔드가 된다.

`deploy/secret.sh` 가 그 자리를 대신한다. 빈 값과 비ASCII 시크릿을 거부한다
(비ASCII 는 `api/security.py` 가 500 으로 거부하는 것과 같은 방향 — 배포
후에 알게 되는 것보다 낫다).

### 4.3 compose 에서는 겪지 않던 것 둘 (실측)

둘 다 파드가 뜨지 않는 오류였고, 매니페스트 주석에 원문을 남겼다.

**하나. `runAsNonRoot` 만으로는 안 된다.** Dockerfile 의 `USER secuagent` 는
이름이라 kubelet 이 비root 인지 검증하지 못한다 —
`CreateContainerConfigError: image has non-numeric user (secuagent), cannot
verify user is non-root`. `runAsUser: 10001` 을 함께 준다. Dockerfile 은
고치지 않는다.

**둘. `/run/secrets` 를 디렉터리로 마운트하면 파드가 죽는다.** 그 경로가 읽기
전용이 되고, kubelet 이 서비스어카운트 토큰을 넣으려는
`/var/run/secrets/kubernetes.io/serviceaccount` 를 만들지 못해
`RunContainerError` 가 난다(`/var/run` 은 `/run` 의 심볼릭 링크다). compose 는
파일 하나를 마운트해서 이 충돌이 없었다. `subPath` 로 파일만 마운트한다.

이 김에 `automountServiceAccountToken: false` 를 넣었다. 이 백엔드는 쿠버네티스
API 를 부르지 않으므로, 터널로 공개되는 파드가 API 토큰을 들고 있을 이유가 없다.

## 5. 검증

| # | 항목 | 결과 |
|---|---|---|
| 1 | `kubectl -n secu-agent get pods` → `Running` | ✅ 23초 만에 Ready, 재시작 0 |
| 2 | `/healthz` → `{"status":"ok","db":true,"model":"ready"}` | ✅ `db:true` — VM 경계를 넘은 DB 도달까지 증명 |
| 3 | 시크릿 헤더 없이 `POST /ask` | ✅ 401 |
| 4 | 터널 도메인으로 왕복 | ✅ `secu.whoareryu.cloud` — `/healthz` 200, 무인증 401, 인증 200 |
| 5 | `colima stop && colima start` 후 사람 개입 없이 2번 복구 | ✅ |
| 6 | 맥 재부팅 후 사람 개입 없이 2번 복구 | ⏸ LaunchAgent 등록됨, 재부팅 미시행 |

`deploy/secret.sh` 의 fail-closed 도 실측했다 — `TUNNEL_TOKEN` 이 비었을 때
Secret 을 만들지 않고 종료코드 1 로 죽는다.

4번은 인터넷에서 잰 것이다. 브라우저가 닿는 경로 전체 — Cloudflare →
클러스터의 cloudflared → ClusterIP → 백엔드 → VM 경계를 넘어 Docker Desktop
의 pgvector — 가 한 번에 검증된다. 공개 호스트명은
`secu.whoareryu.cloud` 이고 터널 설정은 Cloudflare 대시보드에 있다(저장소에는
토큰도 라우트도 남기지 않는다).

## 6. 이 설계가 건드리지 않는 것

- `backend/` 전체. Dockerfile 포함
- `frontend/` 전체
- `docker-compose.yml` 의 `db` 서비스
- 새싹 스택과 그 cloudflared
