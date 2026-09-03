"use client";

import { useState } from "react";
import AskPanel from "@/components/AskPanel";
import RightRail from "@/components/RightRail";

// 페르소나는 이 화면이 모른다 — 셸이 쿠키로 정하고 BFF 가 쿠키에서 읽는다.
export default function AskPage() {
  const [query, setQuery] = useState("");
  return (
    <div className="ask-layout">
      <AskPanel query={query} onQueryChange={setQuery} />
      <RightRail query={query} onSelectSample={setQuery} />
    </div>
  );
}
