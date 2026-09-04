"use client";

import { useEffect, useRef, useState } from "react";
import Blueprint from "./Blueprint";

const TOPICS = ["권한 밖 문서 열람", "열람 이력 오류", "권한 설정 변경 요청", "기타"];
const CONTACT_EMAIL = "security-platform@example.com";

const topicBase: React.CSSProperties = {
  flex: "1 1 auto",
  padding: "7px 12px",
  background: "transparent",
  border: 0,
  borderRight: "1px solid var(--color-divider)",
  fontSize: 12.5,
  cursor: "pointer",
  color: "var(--color-text)",
  fontFamily: "var(--font-body)",
  whiteSpace: "nowrap",
};
const topicOn: React.CSSProperties = { ...topicBase, background: "var(--color-accent-700)", color: "var(--color-bg)" };

// 티켓 시스템이 없다. 프로토타입은 전송 후 티켓 번호·담당자 메일을 보여줬지만
// 그런 시스템이 실제로 없어서, 전송 버튼은 mailto: 링크를 열 뿐이고 접수
// 문구도 사실에 맞게 고쳤다.
export default function InquiryDialog({ adminEmail }: { adminEmail: string }) {
  const [open, setOpen] = useState(false);
  const [sent, setSent] = useState(false);
  const [topic, setTopic] = useState(TOPICS[0]);
  const [text, setText] = useState("");
  const 대화상자 = useRef<HTMLDialogElement>(null);
  const 여는_버튼 = useRef<HTMLButtonElement>(null);

  // showModal() 이 포커스 트랩·ESC·배경 inert 를 전부 맡는다. 직접 만든
  // 오버레이는 그 넷을 모두 빠뜨려, 열고 나면 탭이 보이지도 않는 배경 표를
  // 훑고 ESC 는 먹지 않았다.
  useEffect(() => {
    const d = 대화상자.current;
    if (!d) return;
    if (open && !d.open) d.showModal();
    if (!open && d.open) d.close();
  }, [open]);

  // ESC 로 닫혔을 때도 상태를 맞추고 트리거로 포커스를 돌려준다 — 브라우저는
  // close 이벤트만 주고 React 상태는 모른다.
  function 닫힘() {
    setOpen(false);
    여는_버튼.current?.focus();
  }

  const subject = `[secu-agent] ${topic}`;
  const body = `문의자: ${adminEmail}\n문의 유형: ${topic}\n\n${text}`;
  const mailtoHref = `mailto:${CONTACT_EMAIL}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;

  return (
    <>
      <Blueprint className="card" style={{ padding: 22, gap: 14, background: "var(--color-accent-100)" }}>
        <div style={{ display: "flex", alignItems: "flex-start", gap: 20, flexWrap: "wrap" }}>
          <div style={{ flex: 1, minWidth: "min(280px, 100%)" }}>
            <div className="card-kicker">이상이 있나요?</div>
            <p style={{ margin: "6px 0 0", fontSize: 14, lineHeight: 1.65, color: "var(--color-accent-900)" }}>
              보면 안 되는 서류가 열람되었거나 열람 이력이 실제와 다르면 secu-agent 담당자에게 문의하세요.
            </p>
          </div>
          <button
            ref={여는_버튼}
            type="button"
            className="blueprint btn btn-primary"
            style={{ height: 42, minWidth: 180 }}
            onClick={() => {
              setOpen(true);
              setSent(false);
            }}
          >
            담당자에게 문의 / Contact
          </button>
        </div>
        {sent && (
          <div
            style={{
              borderTop: "1px solid var(--color-accent-300)",
              paddingTop: 12,
              fontSize: 13,
              color: "var(--color-accent-900)",
            }}
          >
            메일 앱이 열립니다. 티켓 시스템은 아직 없습니다.
          </div>
        )}
      </Blueprint>

      {/* 항상 렌더한다 — showModal()/close() 가 열고 닫는다. 조건부로 마운트하면
          ref 가 붙기 전에 effect 가 돌아 첫 클릭이 열리지 않는다. */}
      <dialog ref={대화상자} className="dialog" aria-labelledby="inquiry-title" onClose={닫힘}>
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div>
            <div className="card-kicker">Contact · secu-agent 담당자</div>
            <h2
              id="inquiry-title"
              className="dialog-title"
              style={{ fontSize: 24, margin: "4px 0 0" }}
            >
              열람 권한 이상 문의
            </h2>
          </div>
          {/* 라벨이 감싸지도 htmlFor 로 잇지도 않으면 스크린리더는 이 버튼 묶음이
              무엇을 고르는 것인지 말할 수 없다. 유형은 입력 컨트롤이 아니라
              버튼 그룹이므로 role=group + aria-label 로 이름을 준다. */}
          <div className="field" role="group" aria-label="문의 유형 / Type">
            <span style={{ display: "block", fontSize: 13, fontWeight: 600, marginBottom: 7, color: "var(--color-neutral-800)" }}>
              문의 유형 / Type
            </span>
            <div style={{ display: "flex", flexWrap: "wrap", border: "1px solid var(--color-divider)" }}>
              {TOPICS.map((t, i) => (
                <button
                  key={t}
                  type="button"
                  // 선택 상태를 색으로만 전달하면 보조기술에는 같은 버튼 넷으로 들린다.
                  aria-pressed={t === topic}
                  onClick={() => setTopic(t)}
                  style={{
                    ...(t === topic ? topicOn : topicBase),
                    ...(i === TOPICS.length - 1 ? { borderRight: 0 } : {}),
                  }}
                >
                  {t}
                </button>
              ))}
            </div>
          </div>
          <div className="field">
            <label htmlFor="inquiry-details">내용 / Details</label>
            <textarea
              id="inquiry-details"
              className="input"
              style={{ minHeight: 110 }}
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="해당 직원, 문서, 발생 시각을 적어주세요"
            />
          </div>
          <div style={{ fontSize: 12, color: "var(--color-neutral-800)", lineHeight: 1.55 }}>
            메일 본문에 문의자 계정과 문의 내용이 담깁니다. 열람 이력 상세와 문서 본문은 첨부되지 않습니다.
          </div>
          <div className="dialog-actions" style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
            <button className="btn btn-secondary" type="button" onClick={() => setOpen(false)}>
              취소 / Cancel
            </button>
            <a
              className="btn btn-primary"
              href={mailtoHref}
              onClick={() => {
                setOpen(false);
                setSent(true);
              }}
            >
              문의 보내기 / Send
            </a>
          </div>
        </div>
      </dialog>
    </>
  );
}
