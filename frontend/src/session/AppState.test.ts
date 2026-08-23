import { beforeEach, describe, expect, it } from "vitest";
import { appReducer, stepFromPhase, type AppState } from "./AppState";

const base: AppState = {
  sessionId: "sess_1",
  step: "context_select",
  resultTab: "profile",
  policy: null,
  ratings: {},
  preferredContextIds: [],
  contrast: null,
  finalContextIds: [],
  observedContextIds: [],
  selectedMajorId: null,
  hasConfirmedCourses: false,
};

beforeEach(() => window.localStorage.clear());

describe("선호 Context 선택", () => {
  it("정원을 넘기면 가장 먼저 고른 것을 밀어낸다", () => {
    let state = base;
    for (const id of ["game", "media", "school_life"]) {
      state = appReducer(state, { type: "preferred_toggled", contextId: id, max: 2 });
    }
    expect(state.preferredContextIds).toEqual(["media", "school_life"]);
  });

  it("이미 고른 것을 다시 누르면 해제된다", () => {
    let state = appReducer(base, { type: "preferred_toggled", contextId: "game", max: 2 });
    state = appReducer(state, { type: "preferred_toggled", contextId: "game", max: 2 });
    expect(state.preferredContextIds).toEqual([]);
  });
});

describe("전공 선택", () => {
  it("과목 추천을 누르면 과목 탭으로 이동한다", () => {
    const state = appReducer(base, { type: "major_selected", majorId: "hci_ux" });
    expect(state.selectedMajorId).toBe("hci_ux");
    expect(state.resultTab).toBe("subjects");
  });

  it("전공을 고르기 전에는 selected_major_id가 비어 있다", () => {
    expect(base.selectedMajorId).toBeNull();
  });
});

describe("세션 보관", () => {
  it("세션을 시작하면 session_id를 저장한다", () => {
    appReducer(base, { type: "session_started", sessionId: "sess_new" });
    expect(window.localStorage.getItem("trail.session_id")).toBe("sess_new");
  });

  it("처음부터 다시 시작하면 저장된 session_id를 지운다", () => {
    appReducer(base, { type: "session_started", sessionId: "sess_new" });
    appReducer(base, { type: "restart" });
    expect(window.localStorage.getItem("trail.session_id")).toBeNull();
  });
});

describe("서버 phase → 화면 단계", () => {
  it.each([
    ["INTEREST_RATING", "interest_rating"],
    ["CONTEXT_SELECTION", "context_select"],
    ["CONTRAST_PROPOSAL", "contrast_proposal"],
    ["COVERAGE_CHECK", "contrast_proposal"],
    ["QUESTION_LOOP", "question"],
    ["PROFILE_GENERATION", "result"],
    ["DONE", "result"],
  ])("%s → %s", (phase, expected) => {
    expect(stepFromPhase(phase)).toBe(expected);
  });

  it("모르는 phase면 처음부터 시작한다", () => {
    expect(stepFromPhase("SOMETHING_NEW")).toBe("start");
  });
});
