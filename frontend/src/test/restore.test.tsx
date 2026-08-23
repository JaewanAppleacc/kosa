/** 새로고침 후 Session 복원 — 이어가기와 "이어갈 수 없음"을 구분한다. */
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "@/App";
import * as endpoints from "@/api/endpoints";
import { ApiError } from "@/api/errors";
import { resetMockSession } from "@/api/mock/transport";

beforeEach(() => {
  window.localStorage.clear();
  resetMockSession();
});
afterEach(() => vi.restoreAllMocks());

describe("Session 복원", () => {
  it("저장된 session_id가 있으면 이어서 할지 묻는다", async () => {
    window.localStorage.setItem("trail.session_id", "sess_00000000000000000000000000000000");
    render(<App />);
    await screen.findByText("하던 이야기가 있어요");
  });

  it("이어서 하기를 누르면 서버 phase에 맞는 화면으로 간다", async () => {
    const user = userEvent.setup();
    window.localStorage.setItem("trail.session_id", "sess_00000000000000000000000000000000");
    render(<App />);
    await user.click(await screen.findByRole("button", { name: "이어서 하기" }));
    // session_restore_normal.json의 phase는 PROFILE_GENERATION이다 → 결과 화면.
    await screen.findByText(/성격을 유형으로 나누는 검사가 아니에요/);
  });

  it("서버가 재시작돼 세션이 사라졌으면 오류가 아니라 안내로 처리한다", async () => {
    vi.spyOn(endpoints, "restoreSession").mockRejectedValue(
      new ApiError("SESSION_NOT_FOUND", "세션을 찾을 수 없습니다.", 404),
    );
    window.localStorage.setItem("trail.session_id", "sess_gone");
    render(<App />);

    await screen.findByText("이어서 할 검사가 없어요");
    expect(screen.queryByRole("button", { name: "다시 시도" })).not.toBeInTheDocument();
  });

  it("처음부터 시작을 누르면 저장된 session_id를 지운다", async () => {
    const user = userEvent.setup();
    window.localStorage.setItem("trail.session_id", "sess_00000000000000000000000000000000");
    render(<App />);
    await user.click(await screen.findByRole("button", { name: "처음부터 시작" }));

    await screen.findByRole("button", { name: /3분만 해볼까요/ });
    expect(window.localStorage.getItem("trail.session_id")).toBeNull();
  });
});
