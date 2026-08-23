import { useState } from "react";
import { AppStateProvider, useAppState } from "@/session/AppState";
import { loadSessionId } from "@/session/sessionStorage";
import { ContextSelectScreen } from "@/screens/ContextSelectScreen";
import { ContrastProposalScreen } from "@/screens/ContrastProposalScreen";
import { InterestRatingScreen } from "@/screens/InterestRatingScreen";
import { QuestionScreen } from "@/screens/QuestionScreen";
import { RestoreScreen } from "@/screens/RestoreScreen";
import { ResultScreen } from "@/screens/ResultScreen";
import { StartScreen } from "@/screens/StartScreen";

function Router() {
  const { state } = useAppState();
  // 첫 렌더에서 한 번만 읽는다 — 이후 이동은 전역 상태가 결정한다.
  const [storedSessionId, setStoredSessionId] = useState(() => loadSessionId());

  if (state.sessionId === null && storedSessionId !== null) {
    return <RestoreScreen sessionId={storedSessionId} onGiveUp={() => setStoredSessionId(null)} />;
  }

  switch (state.step) {
    case "interest_rating":
      return <InterestRatingScreen />;
    case "context_select":
      return <ContextSelectScreen />;
    case "contrast_proposal":
      return <ContrastProposalScreen />;
    case "question":
      return <QuestionScreen />;
    case "result":
      return <ResultScreen />;
    case "start":
    default:
      return <StartScreen />;
  }
}

export default function App() {
  return (
    <AppStateProvider>
      <Router />
    </AppStateProvider>
  );
}
