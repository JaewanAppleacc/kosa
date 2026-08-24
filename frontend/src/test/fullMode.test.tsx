/**
 * 전체 모드(Context 15개 활성화 + 선호 4개 + 대비 1개) 대응 확인.
 *
 * 실제 값 출처: `trait-vector-v2` 백엔드를 ENABLE_CONTEXT_PACK_RUNTIME=true,
 * ENABLE_CONTEXT_SELECTION_4_PLUS_1=true로 띄우고 GET /contexts를 받아 그대로 옮겼다.
 * 지금 main 백엔드는 3개 / 2+1이지만, 프론트는 이 숫자들을 selection_policy에서만
 * 읽으므로 코드 수정 없이 따라가야 한다 — 그게 깨지지 않는지 고정해두는 테스트다.
 */
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import * as endpoints from "@/api/endpoints";
import { ContextSelectScreen } from "@/screens/ContextSelectScreen";
import { InterestRatingScreen } from "@/screens/InterestRatingScreen";
import { AppStateProvider, type AppState } from "@/session/AppState";

const CONTEXT_IDS = [
  "game", "media", "school_life", "business", "making",
  "volunteer", "sports", "science", "writing", "art_design",
  "travel", "cooking", "fashion_beauty", "history_humanities", "law_politics",
];

/** 전체 모드 catalog — 15개 전부 assessment_supported=true, 선호 4개 고정. */
function fullModeCatalog() {
  return {
    contexts: CONTEXT_IDS.map((id) => ({
      context_id: id,
      label: `이야기-${id}`,
      description: "설명",
      example_activities: [],
      interest_rating_prompt: `${id}에 얼마나 관심이 있나요?`,
      is_core: true,
      assessment_supported: true,
    })),
    selection_policy: {
      preferred_context_min_count: 4,
      preferred_context_max_count: 4,
      contrast_context_count: 1,
      final_context_min_count: 4,
      final_context_max_count: 5,
      coverage_replacement_enabled: false,
    },
  };
}

function renderWith(ui: React.ReactElement, initial: Partial<AppState> = {}) {
  vi.spyOn(endpoints, "fetchContextCatalog").mockResolvedValue(fullModeCatalog());
  return render(<AppStateProvider initial={{ sessionId: "sess_1", ...initial }}>{ui}</AppStateProvider>);
}

afterEach(() => vi.restoreAllMocks());

describe("전체 모드 (15 Context · 선호 4 + 대비 1)", () => {
  it("관심도 평가는 15개를 모두 그리고, 통과 기준을 정책값(4개)으로 말한다", async () => {
    renderWith(<InterestRatingScreen />);

    // 타일마다 5점 스케일 버튼이 붙는다 — "이야기-{id} — {문구}" 형태의 aria-label로 찾는다.
    await screen.findByText("4개 이상 표시해 주세요.");
    const scaleButtons = screen.getAllByRole("button", { name: /^이야기-.+ — / });
    const rated = new Set(scaleButtons.map((b) => b.getAttribute("aria-label")!.split(" — ")[0]));
    expect(rated.size).toBe(15);
    // 2개가 아니라 정책이 준 4개를 요구해야 한다.
    expect(screen.getByText("4개 이상 표시해 주세요.")).toBeInTheDocument();
  });

  it("15개가 전부 선택 가능해지면 '준비 중'으로 막힌 타일이 하나도 없다", async () => {
    renderWith(<ContextSelectScreen />, {
      ratings: Object.fromEntries(CONTEXT_IDS.map((id) => [id, 4])),
    });

    await screen.findByText(/골라주세요/);
    const tiles = screen.getAllByRole("button", { name: /이야기-/ });
    expect(tiles).toHaveLength(15);
    expect(tiles.filter((t) => (t as HTMLButtonElement).disabled)).toHaveLength(0);
  });

  it("4개를 고르기 전에는 넘어갈 수 없고, 4개를 채우면 열린다", async () => {
    const user = userEvent.setup();
    renderWith(<ContextSelectScreen />, {
      ratings: Object.fromEntries(CONTEXT_IDS.map((id) => [id, 4])),
    });

    await screen.findByText(/골라주세요/);
    const next = screen.getByRole("button", { name: /다음|계속/ });

    for (const id of ["game", "media", "school_life"]) {
      await user.click(screen.getByRole("button", { name: new RegExp(`이야기-${id}`) }));
    }
    expect(screen.getByText("3 / 4 선택함")).toBeInTheDocument();
    expect(next).toBeDisabled();

    await user.click(screen.getByRole("button", { name: /이야기-business/ }));
    expect(screen.getByText("4 / 4 선택함")).toBeInTheDocument();
    expect(next).toBeEnabled();
  });

  it("상한(4개)에 도달해도 다섯 번째 선택이 상태를 망가뜨리지 않는다", async () => {
    const user = userEvent.setup();
    renderWith(<ContextSelectScreen />, {
      ratings: Object.fromEntries(CONTEXT_IDS.map((id) => [id, 4])),
    });

    await screen.findByText(/골라주세요/);
    for (const id of ["game", "media", "school_life", "business", "making"]) {
      await user.click(screen.getByRole("button", { name: new RegExp(`이야기-${id}`) }));
    }
    // 상한을 넘겨 고르더라도 화면이 4개를 넘겼다고 표시하면 안 된다.
    expect(screen.queryByText("5 / 4 선택함")).not.toBeInTheDocument();
  });
});
