"use client";

// 앱 전체에 error.tsx 가 하나도 없었다. 클라이언트 렌더 예외를 잡는 곳이
// 없으면 Next 가 화면 전체를 기본 오류 페이지로 바꾼다 — 셸도 네비도
// 사라져서, 사용자는 돌아갈 자리조차 잃는다.
//
// 실제로 그 경로가 있었다: (explain)/documents 가 personas 목록이 비면
// visible(d, undefined) 를 불러 TypeError 를 던졌다.
//
// **오류 내용을 화면에 싣지 않는다.** 이 앱의 예외 메시지에는 페르소나
// 이름이나 문서 제목이 섞일 수 있고, 그것이 곧 존재 확인이 된다 —
// backend/core/agent/policy.py 의 AccessViolation 이 식별자만 담는 것과
// 같은 원칙이다. digest 는 서버 로그와 맞춰볼 수 있는 값이라 남긴다.
export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div style={{ padding: "64px 24px", maxWidth: 560, margin: "0 auto" }}>
      <div className="card-kicker">Error</div>
      <h1 style={{ fontSize: 26, margin: "6px 0 12px" }}>화면을 그리지 못했습니다</h1>
      <p style={{ margin: "0 0 20px", fontSize: 14, lineHeight: 1.7, color: "var(--color-neutral-800)" }}>
        일시적인 문제일 수 있습니다. 다시 시도해도 같으면 허브로 돌아가 주세요.
        오류 내용은 화면에 싣지 않습니다 — 예외 메시지가 문서나 계정의 존재를
        알려주는 경로가 되지 않도록 합니다.
      </p>
      {error.digest && (
        <p style={{ margin: "0 0 20px", fontSize: 12, color: "var(--color-neutral-800)" }}>
          참조 번호 <code>{error.digest}</code>
        </p>
      )}
      <div style={{ display: "flex", gap: 8 }}>
        <button type="button" className="btn btn-primary" onClick={reset}>
          다시 시도 / Retry
        </button>
        <a className="btn btn-secondary" href="/">
          허브로 / Hub
        </a>
      </div>
    </div>
  );
}
