/**
 * 전공 추천 — 관련성 높은 전공과 함께 탐색할 전공을 구분해서 보여준다.
 *
 * 지켜야 할 것:
 * - insufficient_evidence_message가 null이 아니면 목록 대신 그 문구만 보여준다.
 * - relevance_label / evidence_sufficiency는 서버가 준 정성 Label을 그대로 쓴다.
 *   내부 점수는 계약에 아예 없다.
 * - "자세히 보기"(학과 조회)와 "이 전공으로 과목 추천받기"는 서로 다른 행동이다.
 *   학생이 후자를 명시적으로 눌렀을 때만 selected_major_id가 정해진다.
 */
import { useState } from "react";
import { fetchDepartments, fetchMajors } from "@/api/endpoints";
import type { MajorRelevance } from "@/api/contracts";
import { ErrorView } from "@/components/ErrorView";
import { Badge, Button, Card, SectionTitle, Spinner, StateBlock } from "@/components/ui";
import { useAsync } from "@/hooks/useAsync";
import { useAppState } from "@/session/AppState";

export function MajorsScreen() {
  const { state, dispatch } = useAppState();
  const majors = useAsync(
    (signal) => {
      if (!state.sessionId) return Promise.reject(new Error("세션이 없습니다."));
      return fetchMajors(state.sessionId, signal);
    },
    [state.sessionId],
  );

  if (majors.status === "loading" || majors.status === "idle") {
    return (
      <div className="py-16 text-center">
        <Spinner label="전공을 살펴보는 중" />
      </div>
    );
  }
  if (majors.status === "error") return <ErrorView error={majors.error} onRetry={majors.reload} />;

  const data = majors.data;

  // 목록 UI보다 먼저 확인한다 — 근거가 부족하면 순위 자체를 만들지 않는다.
  if (data.insufficient_evidence_message !== null) {
    return (
      <StateBlock
        title="아직 전공을 추천하기엔 일러요"
        description={data.insufficient_evidence_message}
      />
    );
  }

  const isEmpty = data.relevant_majors.length === 0 && data.explore_together_majors.length === 0;
  if (isEmpty) {
    return (
      <StateBlock
        title="연결된 전공이 아직 없어요"
        description="질문에 조금 더 답하면 함께 살펴볼 분야를 찾아볼 수 있어요."
      />
    );
  }

  return (
    <div className="space-y-8">
      {data.relevant_majors.length > 0 ? (
        <section>
          <SectionTitle hint="답변에서 반복해서 나타난 경향과 이어지는 분야예요.">
            관련성이 높게 나타난 전공
          </SectionTitle>
          <ul className="space-y-3">
            {data.relevant_majors.map((major) => (
              <li key={major.major_id}>
                <MajorCard
                  major={major}
                  onSelectForSubjects={() => dispatch({ type: "major_selected", majorId: major.major_id })}
                />
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {data.explore_together_majors.length > 0 ? (
        <section>
          <SectionTitle hint="지금 결론은 아니지만 같이 두고 보면 좋은 분야예요.">
            함께 탐색해볼 전공
          </SectionTitle>
          <ul className="space-y-3">
            {data.explore_together_majors.map((major) => (
              <li key={major.major_id}>
                <MajorCard
                  major={major}
                  onSelectForSubjects={() => dispatch({ type: "major_selected", majorId: major.major_id })}
                />
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  );
}

function MajorCard({
  major,
  onSelectForSubjects,
}: {
  major: MajorRelevance;
  onSelectForSubjects: () => void;
}) {
  const [showDepartments, setShowDepartments] = useState(false);

  return (
    <Card>
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <h3 className="text-[19px]">{major.label}</h3>
        <Badge>{major.relevance_label}</Badge>
        <Badge tone="quiet">근거 {major.evidence_sufficiency}</Badge>
      </div>

      <p className="sub mb-5">
        {major.repeated_context_count > 0
          ? `서로 다른 ${major.repeated_context_count}개 분야의 답변에서 반복해서 나타났어요.`
          : "이번 답변에서 관련된 모습이 확인됐어요."}
      </p>

      <div className="flex flex-wrap gap-2">
        <Button
          variant="secondary"
          size="sm"
          onClick={() => setShowDepartments((v) => !v)}
          aria-expanded={showDepartments}
        >
          {showDepartments ? "학과 접기" : "어떤 학과가 있나요?"}
        </Button>
        <Button size="sm" onClick={onSelectForSubjects}>
          이 전공으로 과목 추천받기
        </Button>
      </div>

      {showDepartments ? <DepartmentList majorId={major.major_id} /> : null}
    </Card>
  );
}

function DepartmentList({ majorId }: { majorId: string }) {
  const departments = useAsync((signal) => fetchDepartments(majorId, signal), [majorId]);

  if (departments.status === "loading" || departments.status === "idle") {
    return (
      <div className="mt-4 py-4 text-center">
        <Spinner label="학과를 불러오는 중" />
      </div>
    );
  }
  if (departments.status === "error") {
    return (
      <div className="mt-4">
        <ErrorView error={departments.error} onRetry={departments.reload} />
      </div>
    );
  }

  // 200 + 빈 목록은 오류가 아니다 — 연결된 학과가 없다는 정상 상태다.
  if (departments.data.departments.length === 0) {
    return (
      <div className="mt-4">
        <StateBlock
          title="지금 시연 데이터에 연결된 학과가 없어요"
          description="다른 전공을 살펴보거나, 나중에 다시 확인해주세요."
        />
      </div>
    );
  }

  return (
    <ul className="mt-5 flex flex-col gap-2 border-t pt-5" style={{ borderColor: "var(--line)" }}>
      {departments.data.departments.map((department) => (
        <li key={department.department_id} className="rounded-2xl p-4" style={{ background: "var(--color-neutral-100)" }}>
          <p className="font-semibold">
            {department.university_name} {department.department_name}
          </p>
          <p className="mut mt-0.5 text-[13.5px]">
            {department.college_name} · {department.region}
            {department.campus ? ` (${department.campus})` : ""}
          </p>
          <p className="mut mt-1.5 text-[12px]">
            {department.source_svy_year}년 기준 ·{" "}
            <a
              href={department.source_url}
              target="_blank"
              rel="noreferrer noopener"
              className="underline underline-offset-2"
              style={{ color: "var(--accent)" }}
            >
              공식 출처
            </a>
          </p>
        </li>
      ))}
    </ul>
  );
}
