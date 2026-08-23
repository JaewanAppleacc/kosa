/**
 * 화면이 멈추지 않는지 확인한다 — 렌더 예외와 복원 세션.
 * (지시서 §8 "Loading·오류·Fallback 상태에서 화면이 멈추지 않는다")
 */
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "@/App";
import * as endpoints from "@/api/endpoints";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { resetMockSession } from "@/api/mock/transport";
import { AppStateProvider } from "@/session/AppState";
import { QuestionScreen } from "@/screens/QuestionScreen";
import type { NextQuestionResponse } from "@/api/contracts";

beforeEach(() => {
  window.localStorage.clear();
  resetMockSession();
  // ErrorBoundary가 잡은 예외를 콘솔로 다시 뱉지 않게 한다(테스트 출력 오염 방지).
  vi.spyOn(console, "error").mockImplementation(() => {});
});
afterEach(() => vi.restoreAllMocks());

function Boom(): never {
  throw new Error("렌더 중 터짐");
}

describe("ErrorBoundary", () => {
  it("렌더 예외가 나도 흰 화면이 아니라 복구 안내를 보여준다", () => {
    render(
      <ErrorBoundary>
        <Boom />
      </ErrorBoundary>,
    );

    expect(screen.getByText("화면을 표시하는 중 문제가 생겼어요")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "다시 시도" })).toBeInTheDocument();
  });

  it("다시 시도를 누르면 정상 화면으로 돌아온다", async () => {
    const user = userEvent.setup();
    let shouldThrow = true;
    function Flaky() {
      if (shouldThrow) throw new Error("한 번만 터짐");
      return <p>정상 화면</p>;
    }

    render(
      <ErrorBoundary>
        <Flaky />
      </ErrorBoundary>,
    );
    shouldThrow = false;
    await user.click(screen.getByRole("button", { name: "다시 시도" }));

    expect(screen.getByText("정상 화면")).toBeInTheDocument();
  });

  it("앱 전체가 ErrorBoundary로 감싸져 있다", async () => {
    // 첫 화면이 쓰는 조회를 렌더 중 예외로 만든다.
    vi.spyOn(endpoints, "createSession").mockImplementation(() => {
      throw new Error("boom");
    });
    render(<App />);
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: /3분만 해볼까요/ }));

    // 예외가 밖으로 새면 트리가 통째로 언마운트돼 아무것도 남지 않는다.
    expect(document.body.textContent).not.toBe("");
  });
});

describe("복원한 세션의 질문 화면", () => {
  const question: NextQuestionResponse = {
    session_id: "sess_1",
    status: "GENERATED",
    question: {
      question_id: "q1",
      context: "media",
      target_traits: [],
      frame_id: "f",
      question_text: "질문",
      options: [
        { option_id: "o1", role_id: "r1", text: "선택지", primary_trait_delta: {}, next_probe: null },
      ],
      contrast_id: null,
    },
    current_context_id: "media",
    questions_asked_in_current_context: 0,
    assessment_complete: false,
  };

  it("확정 목록을 몰라도 레일이 사라지지 않고, 진행 바는 거짓 비율을 그리지 않는다", async () => {
    vi.spyOn(endpoints, "fetchNextQuestion").mockResolvedValue(question);
    render(
      // 복원 직후 상태: sessionId는 있지만 finalContextIds는 비어 있다.
      <AppStateProvider initial={{ sessionId: "sess_1", step: "question" }}>
        <QuestionScreen />
      </AppStateProvider>,
    );

    await screen.findByRole("list", { name: "답변 선택지" });
    // 지금까지 마주친 Context로 레일을 채운다.
    // (레일은 context_observed effect가 dispatch된 뒤에 채워지므로 find로 기다린다.)
    await screen.findByText("내 이야기");
    // 전체 개수를 모르므로 진행 바를 그리지 않는다.
    expect(screen.queryByRole("progressbar")).not.toBeInTheDocument();
  });
});
