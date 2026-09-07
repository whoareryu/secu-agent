#!/usr/bin/env bash
#
# .env 와 gcp-sa.json 을 읽어 클러스터의 Secret 을 만든다.
#
#   ./deploy/secret.sh
#
# **이 스크립트는 커밋되고, 값은 커밋되지 않는다.** 매니페스트에 평문을
# 두지 않으면서도 배포 절차가 저장소 안에 남게 하는 것이 목적이다. 지워진
# docker-compose.tunnel.yml 이 남긴 교훈이다 — 저장소에 있는 유일한 배포
# 절차가 저장소에 없는 파일을 요구하면 그건 절차가 아니다.
#
# compose 는 `${VAR:?}` 로 설정 누락을 기동 실패로 만들었다. 쿠버네티스에는
# 그런 장치가 없어서 Secret 이 비어도 파드는 그냥 뜬다 — 아는 값으로 열린
# 백엔드가 된다. 그 자리를 이 스크립트가 대신 막는다. **닫히는 쪽으로
# 실패한다.**
set -euo pipefail

cd "$(dirname "$0")/.."

NS=secu-agent
NAME=secu-agent

[ -f .env ] || { echo "오류: .env 가 없다. cp .env.example .env 부터." >&2; exit 1; }
[ -f gcp-sa.json ] || { echo "오류: gcp-sa.json 이 없다." >&2; exit 1; }

# shellcheck disable=SC1091
set -a; . ./.env; set +a

# 변수명은 ASCII 여야 한다. bash 의 `local` 은 비ASCII 식별자를 거부하는데,
# 그 거부가 **assignment 전체를 에러 메시지로 출력한다** — 시크릿 값이 그대로
# 터미널에 찍힌다. 함수 이름은 비ASCII 여도 되지만 변수 이름은 안 된다.
필수() {
  local name=$1 value=${!1:-}
  [ -n "$value" ] || { echo "오류: .env 의 $name 이 비어 있다." >&2; exit 1; }
}

필수 BACKEND_SHARED_SECRET
필수 GOOGLE_CLOUD_PROJECT
필수 TUNNEL_TOKEN

# HTTP 헤더 값은 ASCII 만 허용되고, hmac.compare_digest 는 양쪽이 같은
# 비ASCII 문자열이어도 TypeError 로 죽는다. api/security.py 가 이것을 500 으로
# 거부하는데, 배포한 뒤 500 을 보고 알게 되는 것보다 여기서 막는 것이 낫다.
if ! printf '%s' "$BACKEND_SHARED_SECRET" | LC_ALL=C grep -q '^[[:print:]]*$'; then
  echo "오류: BACKEND_SHARED_SECRET 에 비ASCII 문자가 있다." >&2
  echo "      새로 만든다:  openssl rand -base64 32 | tr -d '/+='" >&2
  exit 1
fi

# 비워두면 클러스터 안 이름을 쓴다. 그 이름이 무엇을 가리키는지는
# k8s/db-endpoint.yaml 한 곳에만 있다.
#
# 슈파베이스로 옮길 때는 .env 에 SECUAGENT_DSN 을 적고 db-endpoint.yaml 을
# 지우면 된다. 매니페스트도 백엔드 코드도 고칠 것이 없다.
DSN=${SECUAGENT_DSN:-postgresql://secuagent:secuagent@secu-db:5432/secuagent}

kubectl create namespace "$NS" --dry-run=client -o yaml | kubectl apply -f - >/dev/null

# create --dry-run | apply 는 갱신도 되게 한다. `kubectl create secret` 만
# 쓰면 두 번째 실행이 AlreadyExists 로 죽어서, 값을 바꾸려면 사람이 지우고
# 다시 만들어야 한다.
kubectl create secret generic "$NAME" \
  --namespace "$NS" \
  --from-literal=SECUAGENT_DSN="$DSN" \
  --from-literal=BACKEND_SHARED_SECRET="$BACKEND_SHARED_SECRET" \
  --from-literal=GOOGLE_CLOUD_PROJECT="$GOOGLE_CLOUD_PROJECT" \
  --from-literal=GOOGLE_CLOUD_LOCATION="${GOOGLE_CLOUD_LOCATION:-global}" \
  --from-literal=TUNNEL_TOKEN="$TUNNEL_TOKEN" \
  --from-file=gcp-sa.json=gcp-sa.json \
  --dry-run=client -o yaml | kubectl apply -f -

echo "Secret '$NAME' 을 네임스페이스 '$NS' 에 적용했다."
