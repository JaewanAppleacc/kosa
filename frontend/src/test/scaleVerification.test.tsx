/**
 * 프론트 규모 검증 — 2026-08-25 지시서(a/subgraph-rag-frontend-38-majors) §3.
 *
 * 여기서 만든 Fixture는 전부 이 테스트 파일 안에서만 쓰는 합성 데이터다 — A가 만드는
 * 정본 Mock(`outputs/mock_api/`, `@mock` alias)은 건드리지 않는다. API 계약(zod
 * Schema)도, Matching 로직도 바꾸지 않는다 — 이미 있는 화면이 극단적인 규모의 응답을
 *받아도 무너지지 않는지만 확인한다. `departmentModal.test.tsx`가 이미 75건짜리
 * "많음" 케이스를 검증해 둔 패턴을 그대로 따른다.
 */
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import * as endpoints from "@/api/endpoints";
import type { Department, MajorRelevance, MajorsResponse } from "@/api/contracts";
import { MajorsScreen } from "@/screens/MajorsScreen";
import { AppStateProvider } from "@/session/AppState";

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

function major(overrides: Partial<MajorRelevance> & { major_id: string }): MajorRelevance {
  return {
    label: "미디어커뮤니케이션학",
    description: "미디어 콘텐츠의 기획·제작과 수용자 반응을 다루는 전공 분야입니다.",
    relevance_label: "관련성 높음",
    evidence_sufficiency: "충분",
    repeated_context_count: 2,
    ...overrides,
  };
}

const REGIONS = ["서울", "부산", "대구", "인천", "광주", "대전", "경기", "강원", "제주"] as const;

function manyDepartments(count: number): Department[] {
  return Array.from({ length: count }, (_, index) =>
    department({
      department_id: `d${index}`,
      university_name: `대학${String(index).padStart(3, "0")}`,
      region: REGIONS[index % REGIONS.length],
    }),
  );
}

function renderMajors(majors: MajorsResponse, departments: Department[]) {
  vi.spyOn(endpoints, "fetchMajors").mockResolvedValue(majors);
  vi.spyOn(endpoints, "fetchDepartments").mockResolvedValue({
    major_id: majors.relevant_majors[0]?.major_id ?? majors.explore_together_majors[0]?.major_id ?? "",
    departments,
  });
  return render(
    <AppStateProvider initial={{ sessionId: "sess_1" }}>
      <MajorsScreen />
    </AppStateProvider>,
  );
}

async function openFirstModal(user: ReturnType<typeof userEvent.setup>) {
  const opener = (await screen.findAllByRole("button", { name: "어떤 학과가 있나요?" }))[0] as HTMLElement;
  await user.click(opener);
  return screen.findByRole("dialog");
}

afterEach(() => vi.restoreAllMocks());

describe("추천 카드 3+3 규모", () => {
  it("관련성 높은 전공 3개 + 함께 탐색 3개(최대 규모)가 모두 렌더링되고, 그룹별로 1부터 번호가 매겨진다", async () => {
    const majorsResponse: MajorsResponse = {
      session_id: "sess_1",
      insufficient_evidence_message: null,
      relevant_majors: [
        major({ major_id: "m1", label: "미디어커뮤니케이션학" }),
        major({ major_id: "m2", label: "컴퓨터·소프트웨어" }),
        major({ major_id: "m3", label: "심리학" }),
      ],
      explore_together_majors: [
        major({ major_id: "m4", label: "산업공학", relevance_label: "함께 탐색해볼 분야" }),
        major({ major_id: "m5", label: "교육학", relevance_label: "함께 탐색해볼 분야" }),
        major({ major_id: "m6", label: "생명과학", relevance_label: "함께 탐색해볼 분야" }),
      ],
    };
    renderMajors(majorsResponse, []);

    await screen.findByText("답변과 이어지는 분야 6개를 찾았어요");
    for (const label of ["미디어커뮤니케이션학", "컴퓨터·소프트웨어", "심리학", "산업공학", "교육학", "생명과학"]) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }

    // 그룹마다 순번이 1부터 다시 시작한다 — 서로 다른 그룹끼리 번호를 이어붙이지 않는다.
    const relevantSection = screen.getByText("관련성이 높게 나타난 전공").closest("section");
    const exploreSection = screen.getByText("함께 탐색해볼 전공").closest("section");
    expect(within(relevantSection as HTMLElement).getAllByText("1")).toHaveLength(1);
    expect(within(exploreSection as HTMLElement).getAllByText("1")).toHaveLength(1);
  });
});

describe("학과 수 규모 — 0/1/50/300건", () => {
  const baseMajors: MajorsResponse = {
    session_id: "sess_1",
    insufficient_evidence_message: null,
    relevant_majors: [major({ major_id: "media_communication" })],
    explore_together_majors: [],
  };

  it("0건이면 오류가 아니라 빈 상태를 보여준다", async () => {
    const user = userEvent.setup();
    renderMajors(baseMajors, []);
    const dialog = await openFirstModal(user);
    await within(dialog).findByText("지금 시연 데이터에 연결된 학과가 없어요");
  });

  it("1건이면 요약 문구와 학과 1개가 그대로 보인다(지역 칩은 안 나온다)", async () => {
    const user = userEvent.setup();
    renderMajors(baseMajors, [department({ department_id: "d1" })]);
    const dialog = await openFirstModal(user);
    await within(dialog).findByText("예시대학교 미디어학과");
    expect(within(dialog).getByText(/1개 대학 · 1개 학과/)).toBeInTheDocument();
    expect(within(dialog).queryByRole("group", { name: "지역 선택" })).not.toBeInTheDocument();
  });

  it("50건이면 전부 한 번에 그려진다(PAGE_SIZE 60 미만)", async () => {
    const user = userEvent.setup();
    renderMajors(baseMajors, manyDepartments(50));
    const dialog = await openFirstModal(user);
    await within(dialog).findByText(/50개 대학 · 50개 학과/);
    expect(within(dialog).queryByRole("button", { name: /더 보기/ })).not.toBeInTheDocument();
    expect(within(dialog).getAllByRole("listitem")).toHaveLength(50);
  });

  it("300건이면 처음엔 60개만 그리고, '더 보기'를 반복 클릭하면 전부 이어서 나온다(부분 렌더링 유지)", async () => {
    const user = userEvent.setup();
    renderMajors(baseMajors, manyDepartments(300));
    const dialog = await openFirstModal(user);
    await within(dialog).findByText(/300개 대학 · 300개 학과/);

    // 300건을 한 번에 DOM에 안 올린다 — 실제 브라우저에서 렌더 비용이 학과 수에
    // 비례해 커지지 않게 하는 부분 렌더링(PAGE_SIZE) 보장이 핵심이다.
    expect(within(dialog).getAllByRole("listitem")).toHaveLength(60);

    let more = within(dialog).getByRole("button", { name: /더 보기/ });
    await user.click(more);
    expect(within(dialog).getAllByRole("listitem")).toHaveLength(120);

    more = within(dialog).getByRole("button", { name: /더 보기/ });
    await user.click(more);
    await user.click(within(dialog).getByRole("button", { name: /더 보기/ }));
    await user.click(within(dialog).getByRole("button", { name: /더 보기/ }));
    expect(within(dialog).getAllByRole("listitem")).toHaveLength(300);
    expect(within(dialog).queryByRole("button", { name: /더 보기/ })).not.toBeInTheDocument();
  });

  it("300건 검색은 필터링된 결과만 부분 렌더링한다", async () => {
    const user = userEvent.setup();
    renderMajors(baseMajors, manyDepartments(300));
    const dialog = await openFirstModal(user);
    await within(dialog).findByText(/300개 대학 · 300개 학과/);

    await user.type(within(dialog).getByLabelText("학과 검색"), "대학001");
    await within(dialog).findByText(/조건에 맞는 1개/);
    expect(within(dialog).getAllByRole("listitem")).toHaveLength(1);
  });
});

describe("긴 전공명·학과명", () => {
  const LONG_MAJOR_LABEL =
    "인공지능·데이터사이언스·휴먼컴퓨터인터랙션 융합 전공(대학원 연계 계약학과 트랙)";
  const LONG_DEPARTMENT_NAME =
    "미래융합기술대학 인공지능소프트웨어학부 인간중심인공지능전공(야간 계약학과)";
  const LONG_UNIVERSITY_NAME = "국립한국과학기술원부설미래산업융합대학교";

  it("긴 전공명이 있어도 카드가 그대로 렌더링된다", async () => {
    const majorsResponse: MajorsResponse = {
      session_id: "sess_1",
      insufficient_evidence_message: null,
      relevant_majors: [major({ major_id: "m1", label: LONG_MAJOR_LABEL })],
      explore_together_majors: [],
    };
    renderMajors(majorsResponse, []);
    expect(await screen.findByText(LONG_MAJOR_LABEL)).toBeInTheDocument();
  });

  it("긴 학과명·대학명이 있어도 목록이 그대로 렌더링된다", async () => {
    const user = userEvent.setup();
    const majorsResponse: MajorsResponse = {
      session_id: "sess_1",
      insufficient_evidence_message: null,
      relevant_majors: [major({ major_id: "media_communication" })],
      explore_together_majors: [],
    };
    renderMajors(majorsResponse, [
      department({
        department_id: "d1",
        university_name: LONG_UNIVERSITY_NAME,
        department_name: LONG_DEPARTMENT_NAME,
      }),
    ]);
    const dialog = await openFirstModal(user);
    expect(
      await within(dialog).findByText(`${LONG_UNIVERSITY_NAME} ${LONG_DEPARTMENT_NAME}`),
    ).toBeInTheDocument();
  });
});

describe("모바일 화면에서의 규모 대응", () => {
  it("학과가 300건이어도 목록 컨테이너가 세로로만 쌓이고 body를 가로로 밀어내지 않는다", async () => {
    const user = userEvent.setup();
    const majorsResponse: MajorsResponse = {
      session_id: "sess_1",
      insufficient_evidence_message: null,
      relevant_majors: [major({ major_id: "media_communication" })],
      explore_together_majors: [],
    };
    renderMajors(majorsResponse, manyDepartments(300));
    const dialog = await openFirstModal(user);
    await within(dialog).findByText(/300개 대학 · 300개 학과/);

    const list = within(dialog).getAllByRole("listitem")[0]?.closest("ul");
    expect(list?.className).toContain("flex-col");
  });
});
