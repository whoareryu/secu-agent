import Blueprint from "@/components/Blueprint";

// 이 화면의 모든 패널은 자기 주장의 뒷받침을 함께 말한다.
//
// evidence 를 선택값이 아니라 필수 prop 으로 둔 이유: 뒷받침 없는 패널을
// 만들 수 없게 하기 위해서다. 이 프로젝트는 "저장하는 곳이 없는 값을
// 화면에 두지 않는다"를 지켜왔고, 주장만 적힌 설명 화면은 그 규칙을
// 스스로 깨는 것이다.
type Evidence = "live" | "measured" | "schema";

const 배지: Record<Evidence, { 글: string; 설명: string }> = {
  live: { 글: "지금 실행됨", 설명: "이 숫자는 이 페이지를 열 때 실제로 계산됐습니다." },
  measured: { 글: "측정 기록", 설명: "라이브가 아닙니다. 아래 출처에서 측정된 값입니다." },
  schema: { 글: "스키마", 설명: "코드와 스키마에서 그대로 읽은 것입니다." },
};

// source 는 evidence 가 "measured" 일 때만 필수다 — 분기 유니온으로
// 타입 수준에서 강제한다. 출처 없는 인용 패널은 컴파일되지 않는다.
type Props =
  | { evidence: "live" | "schema"; source?: never; kicker: string; title: string; children: React.ReactNode }
  | { evidence: "measured"; source: string; kicker: string; title: string; children: React.ReactNode };

const 배지_색: Record<Evidence, string> = {
  live: "tag-accent",
  measured: "tag-accent-2",
  schema: "tag-neutral",
};

export default function EvidencePanel(props: Props) {
  const { evidence, kicker, title, children } = props;
  const source = props.evidence === "measured" ? props.source : undefined;
  const { 글, 설명 } = 배지[evidence];

  return (
    <Blueprint className="card" style={{ padding: 20, gap: 12 }}>
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 16 }}>
        <div>
          <div className="card-kicker">{kicker}</div>
          <div className="card-title" style={{ marginTop: 4 }}>
            {title}
          </div>
        </div>
        <span className={`tag ${배지_색[evidence]}`} style={{ whiteSpace: "nowrap" }}>
          {글}
        </span>
      </div>
      <p style={{ margin: 0, fontSize: 12, color: "var(--color-neutral-600)" }}>
        {설명}
        {source && ` 출처: ${source}`}
      </p>
      {children}
    </Blueprint>
  );
}

// @ts-expect-error — measured 패널은 source 없이 컴파일되지 않는다.
// 이 줄이 에러를 내지 않게 되는 날(=타입이 느슨해진 날) tsc 가 실패한다.
const _출처_없는_인용: Props = {
  evidence: "measured", kicker: "", title: "", children: null,
};
