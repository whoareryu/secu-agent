import AskForm from "@/components/AskForm";

// 자리만 만든다 — Ask 화면 자체를 다듬는 것은 다음 태스크의 몫이다. 이
// 라우트가 없으면 로그인 후 리다이렉트가 404 로 떨어진다.
export default function AskPage() {
  return <AskForm />;
}
