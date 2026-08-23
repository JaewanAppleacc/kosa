/**
 * 정상 / 빈 결과 / 부분 결과 / 오류를 각각 다르게 렌더링하는지 확인한다.
 * (지시서 §3 "정상, 빈 결과, 부분 결과, 오류 상태를 구분한다")
 */
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import * as endpoints from "@/api/endpoints";
import { ApiError, NetworkError } from "@/api/errors";
import { MajorsScreen } from "@/screens/MajorsScreen";
import { ProfileScreen } from "@/screens/ProfileScreen";
import { SubjectsScreen } from "@/screens/SubjectsScreen";
import { AppStateProvider, type AppState } from "@/session/AppState";
import profilePartial from "@mock/profile_partial__hand_crafted.json";
import majorsNormal from "@mock/majors_normal.json";
import type { CareerProfile, CourseProfile, MajorsResponse } from "@/api/contracts";

/** 조회 함수는 갈아끼우고, 화면이 그 응답을 어떻게 그리는지만 본다. */
function renderWithState(ui: React.ReactElement, initial: Partial<AppState> = {}) {
  return render(
    <AppStateProvider initial={{ sessionId: "sess_1", ...initial }}>{ui}</AppStateProvider>,
  );
}

beforeEach(() => {
  window.localStorage.clear();
});
afterEach(() => vi.restoreAllMocks());

describe("Profile", () => {
  it("부분 Profile(관찰되지 않은 Trait 포함)도 정상적으로 그린다", async () => {
    vi.spyOn(endpoints, "fetchProfile").mockResolvedValue(profilePartial as unknown as CareerProfile);
    renderWithState(<ProfileScreen />);

    await screen.findByText(/성격을 유형으로 나누는 검사가 아니에요/);
    // "답변이 부족하다"(관찰 부족)는 허용이고, 학생의 능력·경험 결핍 표현만 금지다.
    expect(document.body.textContent).not.toMatch(/능력이? ?부족|경험이? ?부족|소질이 없|잘하지 못/);
  });

  it("답변이 없으면 오류가 아니라 '조금 더 답해달라'는 안내를 보여준다", async () => {
    vi.spyOn(endpoints, "fetchProfile").mockRejectedValue(
      new ApiError("EVIDENCE_NOT_READY", "Evidence가 없습니다.", 422),
    );
    renderWithState(<ProfileScreen />);

    await screen.findByText("아직 결과를 만들 답변이 모이지 않았어요");
    expect(screen.queryByRole("button", { name: "다시 시도" })).not.toBeInTheDocument();
  });

  it("네트워크 오류는 다시 시도할 수 있게 한다", async () => {
    vi.spyOn(endpoints, "fetchProfile").mockRejectedValue(new NetworkError(new Error("boom")));
    renderWithState(<ProfileScreen />);

    await screen.findByText("서버에 연결하지 못했어요");
    expect(screen.getByRole("button", { name: "다시 시도" })).toBeInTheDocument();
  });
});

describe("전공", () => {
  it("insufficient_evidence_message가 있으면 목록 대신 안내만 보여준다", async () => {
    vi.spyOn(endpoints, "fetchMajors").mockResolvedValue({
      session_id: "sess_1",
      relevant_majors: [],
      explore_together_majors: [],
      insufficient_evidence_message: "아직 관련도를 계산하기에 답변이 부족합니다.",
    } satisfies MajorsResponse);
    renderWithState(<MajorsScreen />);

    await screen.findByText("아직 전공을 추천하기엔 일러요");
    expect(screen.queryByText("관련성이 높게 나타난 전공")).not.toBeInTheDocument();
  });

  it("학과가 0개여도 오류가 아니라 빈 상태로 보여준다", async () => {
    const user = userEvent.setup();
    vi.spyOn(endpoints, "fetchMajors").mockResolvedValue(majorsNormal as unknown as MajorsResponse);
    vi.spyOn(endpoints, "fetchDepartments").mockResolvedValue({
      major_id: "hci_ux",
      departments: [],
    });
    renderWithState(<MajorsScreen />);

    await screen.findByText("관련성이 높게 나타난 전공");
    await user.click(screen.getAllByRole("button", { name: "어떤 학과가 있나요?" })[0] as HTMLElement);

    await screen.findByText("지금 시연 데이터에 연결된 학과가 없어요");
  });
});

describe("과목", () => {
  const postOffering: CourseProfile = {
    session_id: "sess_1",
    source: "POST_OFFERING",
    recommendations: [
      {
        subject_id: "subj_alt",
        label: "정보",
        category: "alternative",
        is_actually_offered: true,
        reason: "원래 희망했던 데이터 과학 대신 들을 수 있어요.",
        replaces_subject_id: "subj_gone",
      },
    ],
    unresolved_candidates: [
      { raw_text: "정체불명 과목ABC", matched_subject_id: null, confidence: "unmatched", requires_user_confirmation: true },
    ],
    unavailable_subjects: [{ subject_id: "subj_gone", label: "데이터 과학", reason: "올해 개설되지 않아요." }],
  };

  it("미개설 과목·대체 과목·확인 필요 과목을 각각 다른 영역에 보여준다", async () => {
    vi.spyOn(endpoints, "fetchSubjects").mockResolvedValue(postOffering);
    renderWithState(<SubjectsScreen />, { selectedMajorId: "industrial_engineering" });

    await screen.findByText("대체 과목");
    expect(screen.getByText("이번에 들을 수 없는 과목")).toBeInTheDocument();
    expect(screen.getByText("데이터 과학")).toBeInTheDocument();
    expect(screen.getByText("확인이 필요한 과목")).toBeInTheDocument();
    expect(screen.getByText("정체불명 과목ABC")).toBeInTheDocument();
    // 확정을 마쳤으므로 업로드 패널은 더 이상 보이지 않는다.
    expect(screen.queryByText("학교 편제표 올리기")).not.toBeInTheDocument();
  });
});
