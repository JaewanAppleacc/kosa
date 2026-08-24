/**
 * "선호 Context 4개 + Contrast 1개" 정책 — 2026-08-24 지시서
 * (a/context-selection-4-plus-1) §7.
 *
 * 프론트는 GET /contexts의 selection_policy만 보고 동작해야 한다 — 4, 5를 별도
 * 상수로 복제하지 않는다. 실제 커밋된 Mock JSON(outputs/mock_api/contexts_normal.json,
 * Flag OFF 2+1 값)은 절대 건드리지 않는다 — 대신 fetchContextCatalog를 직접 Mock해
 * 4+1 모양의 합성 Catalog를 주입한다(실제 백엔드·Mock 파일과 완전히 분리된 순수
 * 프론트 단위 테스트).
 */
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import * as endpoints from "@/api/endpoints";
import type { ContextCatalog } from "@/api/endpoints";
import { ContextSelectScreen } from "@/screens/ContextSelectScreen";
import { ContrastProposalScreen } from "@/screens/ContrastProposalScreen";
import { AppStateProvider } from "@/session/AppState";

const CONTEXT_LABELS: Record<string, string> = {
  game: "게임", media: "미디어", school_life: "학교생활", sports: "스포츠",
  business: "비즈니스", art_design: "미술·디자인",
};

function makeContext(contextId: string, assessmentSupported = true) {
  return {
    context_id: contextId,
    label: CONTEXT_LABELS[contextId] ?? contextId,
    description: `${contextId} 설명`,
    example_activities: ["예시 활동"],
    interest_rating_prompt: `${contextId}에 관심이 있나요?`,
    is_core: false,
    assessment_supported: assessmentSupported,
  };
}

/** Flag ON(4+1) 모양의 합성 Catalog — 실제 GET /contexts 응답과 같은 구조이지만
 * 이 테스트 파일 안에서만 존재한다(실제 Mock JSON 파일을 전혀 건드리지 않는다). */
function catalog4Plus1(): ContextCatalog {
  return {
    contexts: ["game", "media", "school_life", "sports", "business", "art_design"].map((id) => makeContext(id)),
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

function catalog2Plus1(): ContextCatalog {
  return {
    contexts: ["game", "media", "school_life"].map((id) => makeContext(id)),
    selection_policy: {
      preferred_context_min_count: 2,
      preferred_context_max_count: 2,
      contrast_context_count: 1,
      final_context_min_count: 2,
      final_context_max_count: 3,
      coverage_replacement_enabled: false,
    },
  };
}

afterEach(() => vi.restoreAllMocks());

describe("ContextSelectScreen — 서버 selection_policy만 사용(4, 5 하드코딩 없음)", () => {
  it("Flag ON(4+1) Catalog를 받으면 화면 문구·정원이 4로 표시된다", async () => {
    vi.spyOn(endpoints, "fetchContextCatalog").mockResolvedValue(catalog4Plus1());
    render(
      <AppStateProvider initial={{ sessionId: "sess_1", ratings: { game: 5, media: 5, school_life: 5, sports: 5 } }}>
        <ContextSelectScreen />
      </AppStateProvider>,
    );

    await screen.findByText(/가장 마음이 가는 4개를 골라주세요/);
    expect(screen.getByText("0 / 4 선택함")).toBeInTheDocument();
  });

  it("Flag OFF(2+1) Catalog를 받으면 화면 문구·정원이 2로 표시된다 — 회귀 확인", async () => {
    vi.spyOn(endpoints, "fetchContextCatalog").mockResolvedValue(catalog2Plus1());
    render(
      <AppStateProvider initial={{ sessionId: "sess_1", ratings: { game: 5, media: 5 } }}>
        <ContextSelectScreen />
      </AppStateProvider>,
    );

    await screen.findByText(/가장 마음이 가는 2개를 골라주세요/);
    expect(screen.getByText("0 / 2 선택함")).toBeInTheDocument();
  });

  it("4개를 고르면 다섯 번째는 가장 먼저 고른 것을 밀어내고 정확히 4개를 유지한다", async () => {
    const user = userEvent.setup();
    vi.spyOn(endpoints, "fetchContextCatalog").mockResolvedValue(catalog4Plus1());
    render(
      <AppStateProvider initial={{ sessionId: "sess_1", ratings: { game: 5, media: 5, school_life: 5, sports: 5, business: 5 } }}>
        <ContextSelectScreen />
      </AppStateProvider>,
    );
    await screen.findByText(/가장 마음이 가는 4개를 골라주세요/);

    for (const label of ["게임", "미디어", "학교생활", "스포츠"]) {
      await user.click(screen.getByRole("button", { name: new RegExp(label) }));
    }
    expect(screen.getByText("4 / 4 선택함")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /비즈니스/ }));
    // 정원 4를 유지 — 가장 먼저 고른 "게임"이 밀려나고 "비즈니스"가 들어온다.
    expect(screen.getByText("4 / 4 선택함")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /게임/ })).toHaveAttribute("aria-pressed", "false");
    expect(screen.getByRole("button", { name: /비즈니스/ })).toHaveAttribute("aria-pressed", "true");
  });

  it("assessment_supported=false 또는 관심도 미입력 Context는 고를 수 없다", async () => {
    vi.spyOn(endpoints, "fetchContextCatalog").mockResolvedValue({
      contexts: [makeContext("game"), makeContext("media"), makeContext("school_life", false), makeContext("sports")],
      selection_policy: catalog4Plus1().selection_policy,
    });
    render(
      <AppStateProvider initial={{ sessionId: "sess_1", ratings: { game: 5, media: 5 } }}>
        <ContextSelectScreen />
      </AppStateProvider>,
    );
    await screen.findByText(/가장 마음이 가는 4개를 골라주세요/);

    expect(screen.getByRole("button", { name: /학교생활/ })).toBeDisabled(); // assessment_supported=false
    expect(screen.getByRole("button", { name: /스포츠/ })).toBeDisabled(); // 관심도 미입력
    expect(screen.getByRole("button", { name: /게임/ })).not.toBeDisabled();
  });
});

describe("ContrastProposalScreen — 서버 selection_policy만 사용, 4/5 하드코딩 없음", () => {
  it("수락 시 총 5개·거절 시 4개 문구가 실제 선택 개수에서 계산된다(4+1)", async () => {
    vi.spyOn(endpoints, "fetchContextCatalog").mockResolvedValue(catalog4Plus1());
    render(
      <AppStateProvider
        initial={{
          sessionId: "sess_1",
          preferredContextIds: ["game", "media", "school_life", "sports"],
          contrast: { session_id: "sess_1", contrast_context_id: "business", contrast_reason: "새로운 관점", coverage_replacement_offered: [] },
        }}
      >
        <ContrastProposalScreen />
      </AppStateProvider>,
    );

    await screen.findByText("이 제안은 꼭 받아들이지 않아도 괜찮아요 — 수락하면 총 5개, 거절하면 4개로 시작해요.");
    const list = screen.getByText("이번에 살펴볼 이야기").nextElementSibling as HTMLElement;
    expect(within(list).getAllByRole("listitem")).toHaveLength(5);
  });

  it("수락 시 총 3개·거절 시 2개 문구가 실제 선택 개수에서 계산된다(2+1, 회귀 확인)", async () => {
    vi.spyOn(endpoints, "fetchContextCatalog").mockResolvedValue(catalog2Plus1());
    render(
      <AppStateProvider
        initial={{
          sessionId: "sess_1",
          preferredContextIds: ["game", "media"],
          contrast: { session_id: "sess_1", contrast_context_id: "school_life", contrast_reason: "새로운 관점", coverage_replacement_offered: [] },
        }}
      >
        <ContrastProposalScreen />
      </AppStateProvider>,
    );

    await screen.findByText("이 제안은 꼭 받아들이지 않아도 괜찮아요 — 수락하면 총 3개, 거절하면 2개로 시작해요.");
  });

  it("수락 클릭 시 선호 4개 + Contrast 1개(5개)로 confirmContexts를 호출한다", async () => {
    const user = userEvent.setup();
    vi.spyOn(endpoints, "fetchContextCatalog").mockResolvedValue(catalog4Plus1());
    const confirmSpy = vi.spyOn(endpoints, "confirmContexts").mockResolvedValue({
      session_id: "sess_1", final_context_ids: ["game", "media", "school_life", "sports", "business"], processing_order: [],
    });
    render(
      <AppStateProvider
        initial={{
          sessionId: "sess_1",
          preferredContextIds: ["game", "media", "school_life", "sports"],
          contrast: { session_id: "sess_1", contrast_context_id: "business", contrast_reason: "새로운 관점", coverage_replacement_offered: [] },
        }}
      >
        <ContrastProposalScreen />
      </AppStateProvider>,
    );
    await screen.findByText(/이야기도 함께 볼까요\?/);
    await user.click(screen.getByRole("button", { name: /좋아요, 시작할게요/ }));

    expect(confirmSpy).toHaveBeenCalledWith("sess_1", ["game", "media", "school_life", "sports", "business"]);
  });

  it("거절 클릭 시 선호 4개만으로 confirmContexts를 호출한다", async () => {
    const user = userEvent.setup();
    vi.spyOn(endpoints, "fetchContextCatalog").mockResolvedValue(catalog4Plus1());
    const confirmSpy = vi.spyOn(endpoints, "confirmContexts").mockResolvedValue({
      session_id: "sess_1", final_context_ids: ["game", "media", "school_life", "sports"], processing_order: [],
    });
    render(
      <AppStateProvider
        initial={{
          sessionId: "sess_1",
          preferredContextIds: ["game", "media", "school_life", "sports"],
          contrast: { session_id: "sess_1", contrast_context_id: "business", contrast_reason: "새로운 관점", coverage_replacement_offered: [] },
        }}
      >
        <ContrastProposalScreen />
      </AppStateProvider>,
    );
    await screen.findByText(/이야기도 함께 볼까요\?/);
    await user.click(screen.getByRole("button", { name: /고른 것만으로 시작/ }));

    expect(confirmSpy).toHaveBeenCalledWith("sess_1", ["game", "media", "school_life", "sports"]);
  });
});

describe("소스 코드 정적 확인 — 4, 5를 프론트 상수로 복제하지 않는다", () => {
  it("ContextSelectScreen/ContrastProposalScreen 소스에 선택 정원을 뜻하는 리터럴 4·5가 없다", async () => {
    const fs = await import("node:fs");
    const path = await import("node:path");
    const root = path.resolve(__dirname, "../..");
    for (const rel of ["src/screens/ContextSelectScreen.tsx", "src/screens/ContrastProposalScreen.tsx"]) {
      const raw = fs.readFileSync(path.join(root, rel), "utf-8");
      // 주석(설명 문구)은 제외하고 실제 코드에서만 "4개"/"5개" 같은 정원 하드코딩을
      // 찾는다 — 주석에는 이 정책을 설명하는 문장이 정당하게 그 숫자를 언급할 수 있다
      // (예: "Flag ON(4+1)에서는 총 5개로 자동으로 달라진다").
      const codeOnly = raw
        .replace(/\/\*[\s\S]*?\*\//g, "")
        .split("\n")
        .map((line) => line.replace(/\/\/.*$/, ""))
        .join("\n");
      expect(codeOnly).not.toMatch(/[^a-zA-Z_]4개/);
      expect(codeOnly).not.toMatch(/[^a-zA-Z_]5개/);
    }
  });
});
