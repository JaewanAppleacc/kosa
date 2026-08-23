/**
 * 결과 시각화(관찰 지도)와 "지나온 질문" 기록이 계약을 지키는지 확인한다.
 *
 * 핵심은 하나다 — 시각화가 늘어나도 화면에 새로 등장하는 숫자는 "관찰된 답변 개수"뿐이고,
 * 점수·퍼센트·막대 길이로 읽힐 수 있는 표현은 생기지 않아야 한다.
 */
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import * as endpoints from "@/api/endpoints";
import type { CareerProfile, NextQuestionResponse } from "@/api/contracts";
import { ProfileScreen } from "@/screens/ProfileScreen";
import { QuestionScreen } from "@/screens/QuestionScreen";
import { AppStateProvider } from "@/session/AppState";
import profileNormal from "@mock/profile_normal.json";

afterEach(() => vi.restoreAllMocks());

describe("결과 관찰 지도", () => {
  function renderProfile() {
    vi.spyOn(endpoints, "fetchProfile").mockResolvedValue(profileNormal as unknown as CareerProfile);
    return render(
      <AppStateProvider initial={{ sessionId: "sess_1" }}>
        <ProfileScreen />
      </AppStateProvider>,
    );
  }

  it("영역 × 이야기 격자를 그리고, 칸마다 답변 개수를 읽어줄 수 있게 한다", async () => {
    renderProfile();

    const table = await screen.findByRole("table", {
      name: /영역별로, 어떤 이야기에서 몇 개의 답변이 나타났는지/,
    });
    // profile_normal.json: "분석과 구조화"는 game에서 2개가 관찰됐다.
    expect(
      within(table).getByRole("button", { name: /분석과 구조화 · .* · 답변 2개/ }),
    ).toBeInTheDocument();
  });

  it("칸을 누르면 그 칸에 실제로 들어간 답변 설명을 그대로 펼친다", async () => {
    const user = userEvent.setup();
    renderProfile();

    const table = await screen.findByRole("table", { name: /영역별로/ });
    const cell = within(table).getByRole("button", { name: /분석과 구조화 · .* · 답변 2개/ });
    await user.click(cell);

    expect(cell).toHaveAttribute("aria-pressed", "true");
    await screen.findByText(/왜 이런 결과가 나왔는지 이유와 원리를 알아가는/);
  });

  it("답변이 없는 칸은 0을 쓰지 않고 누를 수도 없다", async () => {
    renderProfile();

    const table = await screen.findByRole("table", { name: /영역별로/ });
    // "인간과 관계 탐구"는 game에만 있어서 나머지 이야기 칸이 비어 있다.
    const empty = within(table)
      .getAllByRole("button", { name: /인간과 관계 탐구 · .* · 답변 0개/ })
      .at(0);
    expect(empty).toBeDisabled();
    expect(table.textContent).not.toMatch(/\b0\b/);
  });

  it("관찰 지도를 넣어도 '왜 이런 결과가 나왔나요?' 상세는 그대로 남는다", async () => {
    const user = userEvent.setup();
    renderProfile();

    await screen.findByRole("table", { name: /영역별로/ });
    const toggle = screen.getByRole("button", { name: "왜 이런 결과가 나왔나요?" });
    expect(toggle).toHaveAttribute("aria-expanded", "false");

    await user.click(toggle);
    expect(screen.getByRole("button", { name: "근거 접기" })).toBeInTheDocument();
    // 영역 제목이 지도(행 머리)와 상세 목록 양쪽에 나온다.
    expect(screen.getAllByText("분석과 구조화").length).toBeGreaterThan(1);
  });

  it("시각화를 늘려도 퍼센트·소수 점수는 나타나지 않는다", async () => {
    renderProfile();
    await screen.findByRole("table", { name: /영역별로/ });

    expect(document.body.textContent).not.toMatch(/\d+(\.\d+)?%|0\.\d{2}/);
  });
});

describe("지나온 질문", () => {
  const question: NextQuestionResponse = {
    session_id: "sess_1",
    status: "GENERATED",
    question: {
      question_id: "q1",
      context: "media",
      target_traits: [],
      frame_id: "f",
      question_text: "만든 콘텐츠 반응이 예상과 다르면 무엇을 하나요?",
      options: [
        { option_id: "o1", role_id: "r1", text: "왜 그런지부터 살펴본다", primary_trait_delta: {}, next_probe: null },
        { option_id: "o2", role_id: "r2", text: "바로 다시 만들어본다", primary_trait_delta: {}, next_probe: null },
      ],
      contrast_id: null,
    },
    current_context_id: "media",
    questions_asked_in_current_context: 0,
    assessment_complete: false,
  };

  it("답하기 전에는 열 수 없고, 답한 뒤에는 고른 답이 그대로 남는다", async () => {
    const user = userEvent.setup();
    vi.spyOn(endpoints, "fetchNextQuestion").mockResolvedValue(question);
    vi.spyOn(endpoints, "submitAnswer").mockResolvedValue({
      session_id: "sess_1",
      accepted: true,
      next_action: "NEXT_QUESTION",
    });

    render(
      <AppStateProvider initial={{ sessionId: "sess_1", step: "question", finalContextIds: ["media"] }}>
        <QuestionScreen />
      </AppStateProvider>,
    );

    await screen.findByRole("list", { name: "답변 선택지" });
    expect(screen.getByRole("button", { name: "지나온 질문" })).toBeDisabled();

    await user.click(screen.getByRole("button", { name: /왜 그런지부터 살펴본다/ }));
    await screen.findByText("1개 답변함");

    await user.click(screen.getByRole("button", { name: "지나온 질문" }));
    const dialog = await screen.findByRole("dialog");

    expect(within(dialog).getByText("만든 콘텐츠 반응이 예상과 다르면 무엇을 하나요?")).toBeInTheDocument();
    expect(within(dialog).getByText("왜 그런지부터 살펴본다")).toBeInTheDocument();
    // 답을 고칠 수 있다고 오해하게 만드는 요소를 두지 않는다.
    expect(within(dialog).queryByRole("button", { name: /수정|바꾸기|다시 답/ })).not.toBeInTheDocument();
  });
});
