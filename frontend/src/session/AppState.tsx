/**
 * 전역 세션 상태 — 화면 이동과 서버에서 받은 결과의 보관소.
 *
 * 여기 담기는 건 "화면이 다음 단계로 가기 위해 필요한 값"뿐이다.
 * Trait 점수·Evidence 같은 판정 결과는 담지 않는다 — 그건 서버가 계산해서
 * 필요할 때 API로 내려주는 값이지, 프론트가 들고 다닐 상태가 아니다.
 */
import { createContext, useContext, useMemo, useReducer, type ReactNode } from "react";
import type { ContextSelectResponse } from "@/api/contracts";
import type { ContextSelectionPolicy } from "@/api/endpoints";
import { clearSessionId, saveSessionId } from "./sessionStorage";

export type Step =
  | "start"
  | "interest_rating"
  | "context_select"
  | "contrast_proposal"
  | "question"
  | "result";

export type ResultTab = "profile" | "majors" | "subjects" | "graph";

export interface AppState {
  sessionId: string | null;
  step: Step;
  resultTab: ResultTab;
  policy: ContextSelectionPolicy | null;
  ratings: Record<string, number>;
  preferredContextIds: string[];
  contrast: ContextSelectResponse | null;
  finalContextIds: string[];
  /** 학생이 "이 전공으로 과목 추천받기"를 명시적으로 누른 전공. 자동으로 채우지 않는다. */
  selectedMajorId: string | null;
  /** 이 세션에서 /course/confirm까지 마쳤는지. 과목·그래프 화면의 안내 문구가 달라진다. */
  hasConfirmedCourses: boolean;
}

const initialState: AppState = {
  sessionId: null,
  step: "start",
  resultTab: "profile",
  policy: null,
  ratings: {},
  preferredContextIds: [],
  contrast: null,
  finalContextIds: [],
  selectedMajorId: null,
  hasConfirmedCourses: false,
};

export type AppAction =
  | { type: "session_started"; sessionId: string }
  | { type: "session_restored"; sessionId: string; step: Step }
  | { type: "policy_loaded"; policy: ContextSelectionPolicy }
  | { type: "rating_changed"; contextId: string; score: number }
  | { type: "ratings_submitted" }
  | { type: "preferred_toggled"; contextId: string; max: number }
  | { type: "contexts_selected"; contrast: ContextSelectResponse }
  | { type: "contrast_replaced"; contextId: string }
  | { type: "contexts_confirmed"; finalContextIds: string[] }
  | { type: "assessment_completed" }
  | { type: "result_tab_changed"; tab: ResultTab }
  | { type: "major_selected"; majorId: string }
  | { type: "courses_confirmed" }
  | { type: "restart" }
  | { type: "go_to"; step: Step };

export function appReducer(state: AppState, action: AppAction): AppState {
  switch (action.type) {
    case "session_started":
      saveSessionId(action.sessionId);
      return { ...initialState, policy: state.policy, sessionId: action.sessionId, step: "interest_rating" };

    case "session_restored":
      return { ...state, sessionId: action.sessionId, step: action.step };

    case "policy_loaded":
      return { ...state, policy: action.policy };

    case "rating_changed":
      return { ...state, ratings: { ...state.ratings, [action.contextId]: action.score } };

    case "ratings_submitted":
      return { ...state, step: "context_select" };

    case "preferred_toggled": {
      const already = state.preferredContextIds.includes(action.contextId);
      if (already) {
        return {
          ...state,
          preferredContextIds: state.preferredContextIds.filter((id) => id !== action.contextId),
        };
      }
      // 정원이 찼으면 가장 먼저 고른 것을 밀어낸다 — 다시 해제하게 만들지 않는다.
      const next = [...state.preferredContextIds, action.contextId];
      return { ...state, preferredContextIds: next.slice(-action.max) };
    }

    case "contexts_selected":
      return { ...state, contrast: action.contrast, step: "contrast_proposal" };

    case "contrast_replaced":
      return {
        ...state,
        contrast: state.contrast ? { ...state.contrast, contrast_context_id: action.contextId } : null,
      };

    case "contexts_confirmed":
      return { ...state, finalContextIds: action.finalContextIds, step: "question" };

    case "assessment_completed":
      return { ...state, step: "result", resultTab: "profile" };

    case "result_tab_changed":
      return { ...state, resultTab: action.tab };

    case "major_selected":
      return { ...state, selectedMajorId: action.majorId, resultTab: "subjects", step: "result" };

    case "courses_confirmed":
      return { ...state, hasConfirmedCourses: true };

    case "restart":
      clearSessionId();
      return { ...initialState, policy: state.policy };

    case "go_to":
      return { ...state, step: action.step };
  }
}

interface AppStateContextValue {
  state: AppState;
  dispatch: (action: AppAction) => void;
}

const AppStateContext = createContext<AppStateContextValue | null>(null);

export function AppStateProvider({
  children,
  initial,
}: {
  children: ReactNode;
  /** 테스트에서 특정 단계부터 렌더링하기 위한 초기값. 앱 실행 시에는 쓰지 않는다. */
  initial?: Partial<AppState>;
}) {
  const [state, dispatch] = useReducer(appReducer, { ...initialState, ...initial });
  const value = useMemo(() => ({ state, dispatch }), [state]);
  return <AppStateContext.Provider value={value}>{children}</AppStateContext.Provider>;
}

export function useAppState(): AppStateContextValue {
  const value = useContext(AppStateContext);
  if (!value) throw new Error("AppStateProvider 안에서만 useAppState를 쓸 수 있습니다.");
  return value;
}

/** 서버가 돌려준 phase 문자열을 화면 단계로 옮긴다. 모르는 값이면 처음부터 시작한다. */
export function stepFromPhase(phase: string): Step {
  switch (phase) {
    case "INTEREST_RATING":
      return "interest_rating";
    case "CONTEXT_SELECTION":
      return "context_select";
    case "CONTRAST_PROPOSAL":
    case "COVERAGE_CHECK":
      return "contrast_proposal";
    case "QUESTION_LOOP":
      return "question";
    case "PROFILE_GENERATION":
    case "DONE":
      return "result";
    default:
      return "start";
  }
}
