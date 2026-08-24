/**
 * 좁은 화면(모바일)에서 레이아웃이 깨지지 않는지 확인한다.
 *
 * jsdom은 실제 배치를 계산하지 않으므로 픽셀을 재지 않는다. 대신 "좁아지면 반드시
 * 지켜져야 하는 구조적 약속"만 검사한다 — 넘치는 요소는 제 컨테이너 안에서
 * 가로 스크롤되어야 하고, 본문이 화면 밖으로 밀려나면 안 된다.
 */
import { render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import * as endpoints from "@/api/endpoints";
import type { CareerProfile } from "@/api/contracts";
import { ProfileScreen } from "@/screens/ProfileScreen";
import { ResultScreen } from "@/screens/ResultScreen";
import { AppStateProvider } from "@/session/AppState";
import profileNormal from "@mock/profile_normal.json";

afterEach(() => vi.restoreAllMocks());

describe("좁은 화면 레이아웃", () => {
  it("관찰 지도는 표를 줄이지 않고 제 컨테이너 안에서 가로 스크롤한다", async () => {
    vi.spyOn(endpoints, "fetchProfile").mockResolvedValue(profileNormal as unknown as CareerProfile);
    render(
      <AppStateProvider initial={{ sessionId: "sess_1" }}>
        <ProfileScreen />
      </AppStateProvider>,
    );

    const table = await screen.findByRole("table", { name: /영역별로/ });
    // 표 자체가 아니라 감싼 컨테이너가 넘침을 흡수해야 body가 가로로 밀리지 않는다.
    const scroller = table.closest(".tmap-scroll");
    expect(scroller).not.toBeNull();
  });

  it("결과 탭은 개수가 늘어도 줄바꿈 대신 가로 스크롤한다", () => {
    render(
      <AppStateProvider initial={{ sessionId: "sess_1", step: "result" }}>
        <ResultScreen />
      </AppStateProvider>,
    );

    const nav = screen.getByRole("navigation", { name: "결과 보기" });
    expect(nav.className).toContain("overflow-x-auto");
    // 탭이 좁아져 글자가 잘리면 안 된다 — 줄어들지 않게 고정한다.
    for (const tab of within(nav).getAllByRole("button")) {
      expect(tab.className).toContain("shrink-0");
    }
  });
});
