// 알리스트에 있으면 무제한, 밖이면 하루 N회.
//
// 프로세스 메모리에 센다. Vercel 은 인스턴스가 여러 개일 수 있어 완벽하지
// 않지만, 이 상한의 목적은 악의적 공격 차단이 아니라 **요금 폭주 방지**다.
// 인스턴스당 상한이 걸리는 것만으로 그 목적은 달성된다. 정확한 전역 상한이
// 필요해지면 Upstash 같은 외부 저장소가 필요하고, 그것은 이 범위 밖이다.

const counts = new Map<string, { day: string; count: number }>();

function allowlist(): string[] {
  return (process.env.ASK_ALLOWLIST ?? "").split(",").map((s) => s.trim()).filter(Boolean);
}

function dailyLimit(): number {
  return Number(process.env.ASK_DAILY_LIMIT ?? "10");
}

// 날짜 경계는 UTC 로 자른다 — 로컬 시간대를 쓰면 서버 지역에 따라 리셋
// 시점이 달라진다. now 는 테스트에서 날짜 경계를 통제하기 위한 것으로,
// 실제 호출부는 인자를 생략해 현재 시각을 그대로 쓴다.
function utcDay(now: Date): string {
  return now.toISOString().slice(0, 10);
}

export function check(
  email: string,
  now: Date = new Date()
): { allowed: boolean; remaining: number | null } {
  // 알리스트가 비어 있으면 이 목록은 항상 비고, includes 는 항상 false 다 —
  // 기본값이 "모두 무제한" 으로 뒤집히지 않는다.
  if (allowlist().includes(email)) {
    return { allowed: true, remaining: null };
  }

  const day = utcDay(now);
  const limit = dailyLimit();
  const entry = counts.get(email);
  const count = entry && entry.day === day ? entry.count : 0;

  if (count >= limit) {
    return { allowed: false, remaining: 0 };
  }

  const next = count + 1;
  counts.set(email, { day, count: next });
  return { allowed: true, remaining: limit - next };
}
