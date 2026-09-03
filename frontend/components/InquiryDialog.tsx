"use client";

import { useState } from "react";
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
const topicOn: React.CSSProperties = { ...topicBase, background: "var(--color-accent)", color: "var(--color-bg)" };

// 티켓 시스템이 없다. 프로토타입은 전송 후 티켓 번호·담당자 메일을 보여줬지만
// 그런 시스템이 실제로 없어서, 전송 버튼은 mailto: 링크를 열 뿐이고 접수
// 문구도 사실에 맞게 고쳤다.
export default function InquiryDialog({ adminEmail }: { adminEmail: string }) {
  const [open, setOpen] = useState(false);
  const [sent, setSent] = useState(false);
  const [topic, setTopic] = useState(TOPICS[0]);
  const [text, setText] = useState("");

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
          <Blueprint
            as="button"
            className="btn btn-primary"
            style={{ height: 42, minWidth: 180 }}
            onClick={() => {
              setOpen(true);
              setSent(false);
            }}
          >
            담당자에게 문의 / Contact
          </Blueprint>
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

      {open && (
        <div
          className="dialog-backdrop"
          style={{ position: "fixed", inset: 0, display: "grid", placeItems: "center", zIndex: 50 }}
        >
          <Blueprint
            className="dialog"
            style={{ width: "min(520px, 100%)", padding: 26, display: "flex", flexDirection: "column", gap: 16, background: "var(--color-bg)" }}
          >
            <div>
              <div className="card-kicker">Contact · secu-agent 담당자</div>
              <div className="dialog-title" style={{ fontFamily: "var(--font-heading)", fontSize: 24, marginTop: 4 }}>
                열람 권한 이상 문의
              </div>
            </div>
            <div className="field">
              <label>문의 유형 / Type</label>
              <div style={{ display: "flex", flexWrap: "wrap", border: "1px solid var(--color-divider)" }}>
                {TOPICS.map((t, i) => (
                  <button
                    key={t}
                    type="button"
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
              <label>내용 / Details</label>
              <textarea
                className="input"
                style={{ minHeight: 110 }}
                value={text}
                onChange={(e) => setText(e.target.value)}
                placeholder="해당 직원, 문서, 발생 시각을 적어주세요"
              />
            </div>
            <div style={{ fontSize: 12, color: "var(--color-neutral-600)", lineHeight: 1.55 }}>
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
          </Blueprint>
        </div>
      )}
    </>
  );
}
