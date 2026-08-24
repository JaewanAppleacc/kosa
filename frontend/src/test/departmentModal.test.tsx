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
    department_url: null,
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

  it("연결된 학과가 없으면 오류가 아니라 빈 상태 화면을 보여준다", async () => {
    const user = userEvent.setup();
    renderMajors([]);

    const { dialog } = await openModal(user);
    await within(dialog).findByText("지금 시연 데이터에 연결된 학과가 없어요");
    expect(within(dialog).queryByRole("alert")).not.toBeInTheDocument();
  });
});

describe("Department.department_url 표시 정책(2026-08-24 22차 — source_url 비클릭화)", () => {
  it("출처 문구에 source_svy_year가 '대학알리미 {연도}년 공시 기준' 형태로 표시된다", async () => {
    const user = userEvent.setup();
    renderMajors([department({ department_id: "d1", source_svy_year: 2025 })]);

    const { dialog } = await openModal(user);
    expect(await within(dialog).findByText("대학알리미 2025년 공시 기준")).toBeInTheDocument();
  });

  it("공시 문구는 a 태그(클릭 가능한 링크)가 아니다", async () => {
    const user = userEvent.setup();
    renderMajors([department({ department_id: "d1", source_svy_year: 2025 })]);

    const { dialog } = await openModal(user);
    await within(dialog).findByText("대학알리미 2025년 공시 기준");
    // 대학알리미는 모든 학과가 같은 루트 URL을 공유한다 — 클릭 가능한 "공식 출처"
    // 링크로 보이면 학생이 그걸 그 학과의 공식 홈페이지로 오해할 수 있다.
    expect(within(dialog).queryByRole("link", { name: "대학알리미 2025년 공시 기준" })).not.toBeInTheDocument();
  });

  it("source_url은 화면의 어떤 링크의 href로도 쓰이지 않는다", async () => {
    const user = userEvent.setup();
    renderMajors([
      department({
        department_id: "d1",
        university_name: "가나대학교",
        source_url: "https://www.academyinfo.go.kr/",
        department_url: "https://media.gana.ac.kr",
      }),
    ]);

    const { dialog } = await openModal(user);
    await within(dialog).findByText("가나대학교 미디어학과");
    for (const link of within(dialog).getAllByRole("link") as HTMLAnchorElement[]) {
      expect(link.getAttribute("href")).not.toBe("https://www.academyinfo.go.kr/");
    }
  });

  it("department_url이 있으면 '학과 홈페이지 →' 링크를 보여주고, href가 department_url과 정확히 같다", async () => {
    const user = userEvent.setup();
    renderMajors([
      department({
        department_id: "d1",
        university_name: "가나대학교",
        department_url: "https://media.gana.ac.kr",
      }),
    ]);

    const { dialog } = await openModal(user);
    const homepageLink = await within(dialog).findByRole("link", { name: "학과 홈페이지 →" });
    expect(homepageLink).toHaveAttribute("href", "https://media.gana.ac.kr");
    expect(homepageLink).toHaveAttribute("target", "_blank");
    expect(homepageLink).toHaveAttribute("rel", expect.stringContaining("noreferrer"));
    expect(homepageLink).toHaveAttribute("rel", expect.stringContaining("noopener"));
  });

  it("department_url이 null이면 '학과 홈페이지' 링크를 아예 숨긴다", async () => {
    const user = userEvent.setup();
    renderMajors([department({ department_id: "d1", department_url: null })]);

    const { dialog } = await openModal(user);
    await within(dialog).findByText("예시대학교 미디어학과");
    expect(within(dialog).queryByRole("link", { name: "학과 홈페이지 →" })).not.toBeInTheDocument();
    expect(within(dialog).queryByRole("link", { name: /학과 홈페이지/ })).not.toBeInTheDocument();
  });

  it("source_url과 department_url이 서로 다른 값이어도 혼용되지 않는다(각자 정확한 자리에만 쓰인다)", async () => {
    const user = userEvent.setup();
    renderMajors([
      department({
        department_id: "d1",
        source_svy_year: 2024,
        source_url: "https://www.academyinfo.go.kr/",
        department_url: "https://media.gana.ac.kr",
      }),
    ]);

    const { dialog } = await openModal(user);
    // 출처 문구는 여전히 source_svy_year로만 만들어진다(a 태그 아님).
    expect(await within(dialog).findByText("대학알리미 2024년 공시 기준")).toBeInTheDocument();
    expect(within(dialog).queryByRole("link", { name: "대학알리미 2024년 공시 기준" })).not.toBeInTheDocument();
    // 홈페이지 링크는 department_url만 가리킨다.
    const homepageLink = await within(dialog).findByRole("link", { name: "학과 홈페이지 →" });
    expect(homepageLink).toHaveAttribute("href", "https://media.gana.ac.kr");
  });

  it("두 학과가 서로 다른 source_url/department_url 조합을 가져도 각 행이 자기 값만 쓴다", async () => {
    const user = userEvent.setup();
    renderMajors([
      department({
        department_id: "d1",
        university_name: "가나대학교",
        source_url: "https://www.academyinfo.go.kr/",
        department_url: "https://media.gana.ac.kr",
      }),
      department({
        department_id: "d2",
        university_name: "다라대학교",
        source_url: "https://www.academyinfo.go.kr/",
        department_url: null,
      }),
    ]);

    const { dialog } = await openModal(user);
    await within(dialog).findByText("가나대학교 미디어학과");
    const links = within(dialog).getAllByRole("link", { name: "학과 홈페이지 →" });
    // department_url이 있는 학과(가나대학교) 하나만 링크를 갖는다.
    expect(links).toHaveLength(1);
    expect(links[0]).toHaveAttribute("href", "https://media.gana.ac.kr");
  });
});
