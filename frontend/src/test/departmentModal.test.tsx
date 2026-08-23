/**
 * "어떤 학과가 있나요?" 팝업 — 접근성(dialog/Esc/포커스 복원)과, 전국 규모 데이터를
 * 전제로 만든 검색·지역 필터·부분 렌더링이 실제로 동작하는지 확인한다.
 */
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import * as endpoints from "@/api/endpoints";
import type { Department, MajorsResponse } from "@/api/contracts";
import { MajorsScreen } from "@/screens/MajorsScreen";
import { AppStateProvider } from "@/session/AppState";
import majorsNormal from "@mock/majors_normal.json";

function department(overrides: Partial<Department> & { department_id: string }): Department {
  return {
    university_name: "예시대학교",
    campus: null,
    region: "서울",
    department_name: "미디어학과",
    college_name: "사회과학대학",
    admission_unit: null,
    department_status: "EXISTING",
    source_svy_year: 2025,
    source_url: "https://www.academyinfo.go.kr/",
    canonical_major_id: "media_communication",
    ...overrides,
  };
}

const DEPARTMENTS: Department[] = [
  department({ department_id: "d1", university_name: "가나대학교", region: "서울" }),
  department({ department_id: "d2", university_name: "다라대학교", region: "부산", department_name: "신문방송학과" }),
  department({ department_id: "d3", university_name: "마바대학교", region: "부산" }),
];

function renderMajors(departments: Department[] = DEPARTMENTS) {
  vi.spyOn(endpoints, "fetchMajors").mockResolvedValue(majorsNormal as unknown as MajorsResponse);
  vi.spyOn(endpoints, "fetchDepartments").mockResolvedValue({
    major_id: "media_communication",
    departments,
  });
  return render(
    <AppStateProvider initial={{ sessionId: "sess_1" }}>
      <MajorsScreen />
    </AppStateProvider>,
  );
}

async function openModal(user: ReturnType<typeof userEvent.setup>) {
  await screen.findByText("관련성이 높게 나타난 전공");
  const opener = screen.getAllByRole("button", { name: "어떤 학과가 있나요?" })[0] as HTMLElement;
  await user.click(opener);
  return { dialog: await screen.findByRole("dialog"), opener };
}

afterEach(() => vi.restoreAllMocks());

describe("학과 팝업", () => {
  it("버튼을 누르면 dialog가 열리고 학과 목록이 나온다", async () => {
    const user = userEvent.setup();
    renderMajors();

    const { dialog } = await openModal(user);
    await within(dialog).findByText("가나대학교 미디어학과");
    expect(within(dialog).getByText(/2개 대학 · 3개 학과|3개 학과/)).toBeInTheDocument();
  });

  it("Esc를 누르면 닫히고 포커스가 원래 버튼으로 돌아간다", async () => {
    const user = userEvent.setup();
    renderMajors();

    const { opener } = await openModal(user);
    await user.keyboard("{Escape}");

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(document.activeElement).toBe(opener);
  });

  it("검색어로 목록을 좁힌다", async () => {
    const user = userEvent.setup();
    renderMajors();

    const { dialog } = await openModal(user);
    await within(dialog).findByText("가나대학교 미디어학과");

    await user.type(within(dialog).getByLabelText("학과 검색"), "신문방송");

    expect(within(dialog).getByText("다라대학교 신문방송학과")).toBeInTheDocument();
    expect(within(dialog).queryByText("가나대학교 미디어학과")).not.toBeInTheDocument();
  });

  it("지역 칩으로 거르고, 결과가 없으면 오류가 아니라 안내를 보여준다", async () => {
    const user = userEvent.setup();
    renderMajors();

    const { dialog } = await openModal(user);
    await within(dialog).findByText("가나대학교 미디어학과");

    await user.click(within(dialog).getByRole("button", { name: /부산 2/ }));
    expect(within(dialog).queryByText("가나대학교 미디어학과")).not.toBeInTheDocument();
    expect(within(dialog).getByText("마바대학교 미디어학과")).toBeInTheDocument();

    await user.type(within(dialog).getByLabelText("학과 검색"), "없는대학");
    await within(dialog).findByText("조건에 맞는 학과가 없어요");
  });

  it("학과가 많으면 일부만 그리고 '더 보기'로 이어서 보여준다", async () => {
    const user = userEvent.setup();
    const many = Array.from({ length: 75 }, (_, index) =>
      department({
        department_id: `d${index}`,
        university_name: `대학${String(index).padStart(3, "0")}`,
      }),
    );
    renderMajors(many);

    const { dialog } = await openModal(user);
    const more = await within(dialog).findByRole("button", { name: "15개 더 보기" });

    await user.click(more);
    expect(within(dialog).queryByRole("button", { name: /더 보기/ })).not.toBeInTheDocument();
  });

  it("내부 점수를 팝업에서도 노출하지 않는다", async () => {
    const user = userEvent.setup();
    renderMajors();

    const { dialog } = await openModal(user);
    await within(dialog).findByText("가나대학교 미디어학과");
    expect(dialog.textContent).not.toMatch(/\d+(\.\d+)?%|0\.\d{2}/);
  });
});
