/** 결과 화면 — Profile·전공·과목·관계 그래프를 탭으로 묶는다. */
import { Button, ScreenShell, TopBar } from "@/components/ui";
import { SubgraphView } from "@/graph/SubgraphView";
import { useAppState, type ResultTab } from "@/session/AppState";
import { MajorsScreen } from "./MajorsScreen";
import { ProfileScreen } from "./ProfileScreen";
import { SubjectsScreen } from "./SubjectsScreen";

const TABS: Array<{ id: ResultTab; label: string }> = [
  { id: "profile", label: "결과" },
  { id: "majors", label: "전공" },
  { id: "subjects", label: "과목" },
  { id: "graph", label: "관계" },
];

export function ResultScreen() {
  const { state, dispatch } = useAppState();

  return (
    <>
      <TopBar
        right={
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              if (window.confirm("지금까지의 결과를 지우고 처음부터 다시 시작할까요?")) {
                dispatch({ type: "restart" });
              }
            }}
          >
            처음부터
          </Button>
        }
      />
      <ScreenShell wide>
      <nav
        className="mb-6 flex gap-1 overflow-x-auto"
        style={{ boxShadow: "inset 0 -1px 0 var(--color-neutral-200)" }}
        aria-label="결과 보기"
      >
        {TABS.map((tab) => {
          const active = state.resultTab === tab.id;
          return (
            <button
              key={tab.id}
              type="button"
              aria-current={active ? "page" : undefined}
              onClick={() => dispatch({ type: "result_tab_changed", tab: tab.id })}
              className="shrink-0 px-4 py-3 text-[14.5px] font-semibold transition-colors"
              style={{
                fontFamily: "var(--font-heading)",
                color: active ? "var(--accent)" : "var(--color-neutral-600)",
                boxShadow: active ? "inset 0 -2px 0 var(--accent)" : undefined,
              }}
            >
              {tab.label}
            </button>
          );
        })}
      </nav>

      {state.resultTab === "profile" ? <ProfileScreen /> : null}
      {state.resultTab === "majors" ? <MajorsScreen /> : null}
      {state.resultTab === "subjects" ? <SubjectsScreen /> : null}
      {state.resultTab === "graph" ? <SubgraphView /> : null}
      </ScreenShell>
    </>
  );
}
