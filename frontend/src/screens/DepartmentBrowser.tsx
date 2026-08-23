/**
 * "어떤 학과가 있나요?" 팝업 본문.
 *
 * 지금 시연 데이터는 전공당 학과가 몇 개뿐이지만, 나중에 전국 4년제 학과가 들어오면
 * 수백 건이 된다. 그래서 처음부터 검색·지역 필터·부분 렌더링을 전제로 만든다.
 *
 * 여기서 만들어내는 값은 없다 — 요약 숫자·지역 목록 모두 API가 준 학과 목록을
 * 세어본 것뿐이다.
 */
import { useMemo, useState } from "react";
import { fetchDepartments } from "@/api/endpoints";
import type { Department } from "@/api/contracts";
import { ErrorView } from "@/components/ErrorView";
import { Button, Spinner, StateBlock } from "@/components/ui";
import { useAsync } from "@/hooks/useAsync";

/** 한 번에 그리는 최대 개수 — 전국 데이터가 들어와도 첫 렌더가 무거워지지 않게 한다. */
const PAGE_SIZE = 60;

export function DepartmentBrowser({ majorId }: { majorId: string }) {
  const departments = useAsync((signal) => fetchDepartments(majorId, signal), [majorId]);

  if (departments.status === "loading" || departments.status === "idle") {
    return (
      <div className="grid place-items-center py-16">
        <Spinner label="학과를 불러오는 중" />
      </div>
    );
  }
  if (departments.status === "error") {
    return <ErrorView error={departments.error} onRetry={departments.reload} />;
  }

  const list = departments.data.departments;

  // 200 + 빈 목록은 오류가 아니다 — 연결된 학과가 없다는 정상 상태다.
  if (list.length === 0) {
    return (
      <StateBlock
        title="지금 시연 데이터에 연결된 학과가 없어요"
        description="다른 전공을 살펴보거나, 나중에 다시 확인해주세요."
      />
    );
  }

  return <DepartmentList departments={list} />;
}

function DepartmentList({ departments }: { departments: Department[] }) {
  const [query, setQuery] = useState("");
  const [region, setRegion] = useState<string | null>(null);
  const [limit, setLimit] = useState(PAGE_SIZE);

  const regions = useMemo(() => {
    const counted = new Map<string, number>();
    for (const item of departments) counted.set(item.region, (counted.get(item.region) ?? 0) + 1);
    return [...counted.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0], "ko"));
  }, [departments]);

  const universityCount = useMemo(
    () => new Set(departments.map((item) => item.university_name)).size,
    [departments],
  );

  const filtered = useMemo(() => {
    const keyword = query.trim().toLowerCase();
    return departments
      .filter((item) => (region === null ? true : item.region === region))
      .filter((item) => {
        if (keyword === "") return true;
        return [item.university_name, item.department_name, item.college_name, item.region]
          .join(" ")
          .toLowerCase()
          .includes(keyword);
      })
      // 서버 순서에는 의미가 없어서(점수순이 아니다) 찾아보기 쉬운 순서로만 다시 세운다.
      .sort(
        (a, b) =>
          a.region.localeCompare(b.region, "ko") ||
          a.university_name.localeCompare(b.university_name, "ko") ||
          a.department_name.localeCompare(b.department_name, "ko"),
      );
  }, [departments, query, region]);

  const visible = filtered.slice(0, limit);

  return (
    <>
      <div className="mb-4 flex flex-col gap-3">
        <div className="dsearch">
          <svg width="15" height="15" viewBox="0 0 16 16" aria-hidden="true" className="flex-none">
            <circle cx="7" cy="7" r="4.6" fill="none" stroke="currentColor" strokeWidth="1.6" />
            <path d="M10.4 10.4 L14 14" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
          </svg>
          <input
            type="search"
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
              setLimit(PAGE_SIZE);
            }}
            placeholder="대학 이름이나 학과 이름으로 찾기"
            aria-label="학과 검색"
          />
        </div>

        {regions.length > 1 ? (
          <div className="flex flex-wrap gap-1.5" role="group" aria-label="지역 선택">
            <FilterChip active={region === null} onClick={() => setRegion(null)}>
              전체 {departments.length}
            </FilterChip>
            {regions.map(([name, count]) => (
              <FilterChip
                key={name}
                active={region === name}
                onClick={() => {
                  setRegion((current) => (current === name ? null : name));
                  setLimit(PAGE_SIZE);
                }}
              >
                {name} {count}
              </FilterChip>
            ))}
          </div>
        ) : null}
      </div>

      <p className="mut mb-3 text-[12.5px]">
        {universityCount}개 대학 · {departments.length}개 학과
        {filtered.length !== departments.length ? ` · 조건에 맞는 ${filtered.length}개` : ""}
      </p>

      {filtered.length === 0 ? (
        <StateBlock
          title="조건에 맞는 학과가 없어요"
          description="검색어를 지우거나 다른 지역을 골라보세요."
          action={
            <Button
              variant="secondary"
              size="sm"
              onClick={() => {
                setQuery("");
                setRegion(null);
              }}
            >
              조건 지우기
            </Button>
          }
        />
      ) : (
        <>
          <ul className="flex flex-col gap-2">
            {visible.map((department, index) => (
              <li
                key={department.department_id}
                className="drow reveal"
                style={{ animationDelay: `${Math.min(index, 12) * 22}ms` }}
              >
                <p className="font-semibold leading-snug">
                  {department.university_name} {department.department_name}
                </p>
                <p className="mut mt-0.5 text-[13.5px]">
                  {department.college_name} · {department.region}
                  {department.campus ? ` (${department.campus})` : ""}
                </p>
                <p className="mut mt-1.5 text-[12px]">
                  {/* source_url은 출처 표시 전용이다(대학알리미 공식 URL) — 학과 홈페이지
                      버튼으로 쓰지 않는다(README_B §2, 2026-08-24 21차). 권장 문구
                      "대학알리미 {source_svy_year}년 공시 기준"을 그대로 쓴다. */}
                  <a
                    href={department.source_url}
                    target="_blank"
                    rel="noreferrer noopener"
                    className="underline underline-offset-2"
                    style={{ color: "var(--accent)" }}
                  >
                    대학알리미 {department.source_svy_year}년 공시 기준
                  </a>
                </p>

                {/* department_url이 있을 때만 "학과 홈페이지" 버튼을 보여준다 — null이면
                    버튼을 완전히 숨긴다(빈 상태가 정상, 지금 시연 데이터는 전부 null). */}
                {department.department_url !== null ? (
                  <p className="mt-1 text-[12px]">
                    <a
                      href={department.department_url}
                      target="_blank"
                      rel="noreferrer noopener"
                      className="underline underline-offset-2"
                      style={{ color: "var(--accent)" }}
                    >
                      학과 홈페이지
                    </a>
                  </p>
                ) : null}
              </li>
            ))}
          </ul>

          {filtered.length > visible.length ? (
            <div className="mt-4 text-center">
              <Button variant="secondary" size="sm" onClick={() => setLimit((v) => v + PAGE_SIZE)}>
                {filtered.length - visible.length}개 더 보기
              </Button>
            </div>
          ) : null}
        </>
      )}
    </>
  );
}

function FilterChip({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button type="button" className={`fchip${active ? " on" : ""}`} onClick={onClick} aria-pressed={active}>
      {children}
    </button>
  );
}
