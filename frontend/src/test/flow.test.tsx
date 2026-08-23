/**
 * 프론트엔드 E2E — Mock API만으로 Context 평가부터 결과·과목·그래프까지 끝까지 통과한다.
 * 지시서 §3 "테스트"의 사용자 Flow 목록을 그대로 따른다.
 */
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";
import App from "@/App";
import { resetMockSession } from "@/api/mock/transport";

beforeEach(() => {
  window.localStorage.clear();
  resetMockSession();
});

async function startAssessment(user: ReturnType<typeof userEvent.setup>) {
  await user.click(await screen.findByRole("button", { name: /3분만 해볼까요/ }));
  await screen.findByText("요즘 어떤 이야기에 마음이 가나요?");
}

/** 타일 안의 점수 점을 한 번 눌러 바로 평가한다. */
async function rate(
  user: ReturnType<typeof userEvent.setup>,
  label: string,
  score = "아주 좋아해요",
) {
  await user.click(screen.getByRole("button", { name: `${label} — ${score}` }));
}

/** 관심도 평가 → 선호 Context 2개 → Contrast 확정까지. */
async function reachQuestions(user: ReturnType<typeof userEvent.setup>) {
  await startAssessment(user);

  await rate(user, "게임");
  await rate(user, "미디어");

  await user.click(screen.getByRole("button", { name: /다음/ }));
  await screen.findByText("어떤 이야기부터 살펴볼까요?");

  await user.click(screen.getByRole("button", { name: /게임/ }));
  await user.click(screen.getByRole("button", { name: /미디어/ }));
  await user.click(screen.getByRole("button", { name: /다음/ }));

  await screen.findByText(/이야기도 함께 볼까요\?/);
  await user.click(screen.getByRole("button", { name: /좋아요, 시작할게요/ }));
  // 로딩 중에도 진행 표시는 보이므로, 선택지가 실제로 그려질 때까지 기다린다.
  await screen.findByRole("list", { name: "답변 선택지" });
}

describe("Context 평가 및 선택", () => {
  it("최소 개수를 채우기 전에는 다음으로 넘어갈 수 없다", async () => {
    const user = userEvent.setup();
    render(<App />);
    await startAssessment(user);

    expect(screen.getByRole("button", { name: /다음/ })).toBeDisabled();
    // 최소 개수는 서버 정책(GET /contexts)에서 온다.
    expect(screen.getByText("2개 이상 표시해 주세요.")).toBeInTheDocument();
  });

  it("한 번의 클릭으로 점수가 매겨진다", async () => {
    const user = userEvent.setup();
    render(<App />);
    await startAssessment(user);

    await rate(user, "게임");
    expect(screen.getByText("15개 중 1개")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /다음/ })).toBeDisabled();

    await rate(user, "미디어");
    expect(screen.getByRole("button", { name: /다음/ })).toBeEnabled();
  });

  it("서버가 받아주지 않을 분야는 고르기 전에 막고 이유를 보여준다", async () => {
    const user = userEvent.setup();
    render(<App />);
    await startAssessment(user);
    await rate(user, "게임");
    await rate(user, "미디어");
    await user.click(screen.getByRole("button", { name: /다음/ }));
    await screen.findByText("어떤 이야기부터 살펴볼까요?");

    // 평가했고 질문도 준비된 것만 고를 수 있다.
    expect(screen.getByRole("button", { name: /게임/ })).toBeEnabled();
    // 질문 흐름 미지원 → 고를 수 없다(서버가 422로 거부하는 값).
    expect(screen.getByRole("button", { name: /스포츠/ })).toBeDisabled();
    // 지원 Context지만 관심도를 안 매김 → 역시 서버가 거부한다.
    expect(screen.getByRole("button", { name: /학교생활/ })).toBeDisabled();
  });
});

describe("질문 응답과 다음 질문 이동", () => {
  it("답변하면 다음 질문으로 넘어간다", async () => {
    const user = userEvent.setup();
    render(<App />);
    await reachQuestions(user);

    expect(screen.getByText("0개 답변함")).toBeInTheDocument();
    const options = within(screen.getByRole("list", { name: "답변 선택지" })).getAllByRole("button");
    await user.click(options[0] as HTMLElement);

    await waitFor(() => expect(screen.getByText("1개 답변함")).toBeInTheDocument());
  });

  it("진행률 퍼센트를 표시하지 않는다", async () => {
    const user = userEvent.setup();
    render(<App />);
    await reachQuestions(user);

    expect(document.body.textContent).not.toMatch(/\d+\s*%/);
  });
});

describe("결과 화면", () => {
  /** Mock 시나리오: Context 3개 × 5문항을 모두 답하면 ASSESSMENT_COMPLETE가 온다. */
  async function answerEverything(user: ReturnType<typeof userEvent.setup>) {
    // 답변이 실제로 반영될 때까지 기다린 뒤 다음 질문으로 넘어간다.
    // 마지막 답변에서는 결과 화면으로 이동해 진행 표시가 사라지므로 거기서 멈춘다.
    for (let i = 0; i < 20; i += 1) {
      const list = await screen.findByRole("list", { name: "답변 선택지" }).catch(() => null);
      if (!list) break;
      await user.click(within(list).getAllByRole("button")[0] as HTMLElement);
      const advanced = await screen.findByText(`${i + 1}개 답변함`).catch(() => null);
      if (!advanced) break;
    }
  }

  it("검사를 마치면 Profile 카드가 나온다", async () => {
    const user = userEvent.setup();
    render(<App />);
    await reachQuestions(user);
    await answerEverything(user);

    await screen.findByText(/성격을 유형으로 나누는 검사가 아니에요/);
    expect(screen.getByText(/유형으로 나누는 검사가 아니에요/)).toBeInTheDocument();
  });

  it("전공 탭에서 정성 Label만 보여주고 내부 점수를 노출하지 않는다", async () => {
    const user = userEvent.setup();
    render(<App />);
    await reachQuestions(user);
    await answerEverything(user);
    await screen.findByText(/성격을 유형으로 나누는 검사가 아니에요/);

    await user.click(screen.getByRole("button", { name: "전공" }));
    await screen.findByText("관련성이 높게 나타난 전공");

    expect(screen.getByText("관련성 높음")).toBeInTheDocument();
    // 0.67 / 84% 같은 내부 점수 형태가 화면에 없어야 한다.
    expect(document.body.textContent).not.toMatch(/\d+\.\d{2}\b/);
    expect(document.body.textContent).not.toMatch(/\d+\s*%/);
  });

  it("과목 탭은 전공을 고르기 전에는 안내만 보여준다", async () => {
    const user = userEvent.setup();
    render(<App />);
    await reachQuestions(user);
    await answerEverything(user);
    await screen.findByText(/성격을 유형으로 나누는 검사가 아니에요/);

    await user.click(screen.getByRole("button", { name: "과목" }));
    await screen.findByText("어떤 전공으로 과목을 볼까요?");
  });

  it("전공을 고르면 PRE_SURVEY 과목 추천이 나온다", async () => {
    const user = userEvent.setup();
    render(<App />);
    await reachQuestions(user);
    await answerEverything(user);
    await screen.findByText(/성격을 유형으로 나누는 검사가 아니에요/);

    await user.click(screen.getByRole("button", { name: "전공" }));
    await screen.findByText("관련성이 높게 나타난 전공");
    await user.click(screen.getAllByRole("button", { name: "이 전공으로 과목 추천받기" })[0] as HTMLElement);

    // 개설 여부 미확정이므로 "핵심 과목"이 아니라 "우선 희망 과목"으로 표현한다.
    await screen.findByText("학교 편제표 올리기");
    expect(screen.queryByText("핵심 과목")).not.toBeInTheDocument();
  });

  it("관계 그래프를 그리고 Obsidian Export를 제공한다", async () => {
    const user = userEvent.setup();
    render(<App />);
    await reachQuestions(user);
    await answerEverything(user);
    await screen.findByText(/성격을 유형으로 나누는 검사가 아니에요/);

    await user.click(screen.getByRole("button", { name: "관계" }));
    await screen.findByRole("img", { name: /관계 그래프/ });
    expect(screen.getByRole("button", { name: "Markdown 내려받기" })).toBeInTheDocument();
  });
});
