/**
 * 전공 추천 — 관련성 높은 전공과 함께 탐색할 전공을 구분해서 보여준다.
 *
 * 지켜야 할 것:
 * - insufficient_evidence_message가 null이 아니면 목록 대신 그 문구만 보여준다.
 * - relevance_label / evidence_sufficiency는 서버가 준 정성 Label을 그대로 쓴다.
 *   내부 점수는 계약에 아예 없고, 퍼센트·막대 같은 형태로 되살리지도 않는다.
 * - 카드에 붙는 번호는 "서버가 내려준 목록 순서"일 뿐이다. 그룹 안에서만 매기고,
 *   서로 다른 그룹끼리 번호를 이어붙이지 않는다(같은 그룹 안에서만 비교 가능한 순서다).
 * - "어떤 학과가 있나요?"(팝업 조회)와 "이 전공으로 과목 추천받기"는 서로 다른 행동이다.
 *   학생이 후자를 명시적으로 눌렀을 때만 selected_major_id가 정해진다.
 */
import { useMemo, useState } from "react";
import { fetchMajors } from "@/api/endpoints";
import type { MajorRelevance } from "@/api/contracts";
import { ErrorView } from "@/components/ErrorView";
import { Badge, Button, Card, Spinner, StateBlock } from "@/components/ui";
import { Modal } from "@/components/ui/Modal";
import { useAsync } from "@/hooks/useAsync";
import { useAppState } from "@/session/AppState";
import { DepartmentBrowser } from "./DepartmentBrowser";

interface Group {
  id: string;
  title: string;
  /** 필터 칩에 쓰는 짧은 이름. 제목을 잘라 쓰지 않는다. */
  chipLabel: string;
  hint: string;
  majors: MajorRelevance[];
}

export function MajorsScreen() {
  const { state, dispatch } = useAppState();
  const [openMajor, setOpenMajor] = useState<MajorRelevance | null>(null);
  const [activeGroupId, setActiveGroupId] = useState<string | null>(null);

  const majors = useAsync(
    (signal) => {
      if (!state.sessionId) return Promise.reject(new Error("세션이 없습니다."));
      return fetchMajors(state.sessionId, signal);
    },
    [state.sessionId],
  );

  const data = majors.status === "success" ? majors.data : null;

  const groups = useMemo<Group[]>(() => {
    if (data === null) return [];
    const built: Group[] = [
      {
        id: "relevant",
        title: "관련성이 높게 나타난 전공",
        chipLabel: "관련성 높음",
        hint: "답변에서 반복해서 나타난 경향과 이어지는 분야예요. 답변과 가깝게 나타난 순서로 놓았어요.",
        majors: data.relevant_majors,
      },
      {
        id: "explore",
        title: "함께 탐색해볼 전공",
        chipLabel: "함께 탐색",
        hint: "지금 결론은 아니지만 같이 두고 보면 좋은 분야예요.",
        majors: data.explore_together_majors,
      },
    ];
    return built.filter((group) => group.majors.length > 0);
  }, [data]);

  if (majors.status === "loading" || majors.status === "idle") {
    return (
      <div className="py-16 text-center">
        <Spinner label="전공을 살펴보는 중" />
      </div>
    );
  }
  if (majors.status === "error") return <ErrorView error={majors.error} onRetry={majors.reload} />;
  if (data === null) return null;

  // 목록 UI보다 먼저 확인한다 — 근거가 부족하면 순위 자체를 만들지 않는다.
  if (data.insufficient_evidence_message !== null) {
    return (
      <StateBlock
        title="아직 전공을 추천하기엔 일러요"
        description={data.insufficient_evidence_message}
      />
    );
  }

  if (groups.length === 0) {
    return (
      <StateBlock
        title="연결된 전공이 아직 없어요"
        description="질문에 조금 더 답하면 함께 살펴볼 분야를 찾아볼 수 있어요."
      />
    );
  }

  const total = groups.reduce((sum, group) => sum + group.majors.length, 0);
  const shown = activeGroupId === null ? groups : groups.filter((group) => group.id === activeGroupId);

  return (
    <div className="flex flex-col gap-7">
      <div>
        <h2 className="text-[22px] leading-[1.4]">답변과 이어지는 분야 {total}개를 찾았어요</h2>
        <p className="sub mt-1.5">
          아래 묶음은 정해진 결론이 아니라, 지금까지의 답변에서 함께 살펴볼 만한 분야예요.
        </p>

        {groups.length > 1 ? (
          <div className="mt-4 flex flex-wrap gap-1.5" role="group" aria-label="전공 묶음 고르기">
            <button
              type="button"
              className={`fchip${activeGroupId === null ? " on" : ""}`}
              aria-pressed={activeGroupId === null}
              onClick={() => setActiveGroupId(null)}
            >
              전체 {total}
            </button>
            {groups.map((group) => (
              <button
                key={group.id}
                type="button"
                className={`fchip${activeGroupId === group.id ? " on" : ""}`}
                aria-pressed={activeGroupId === group.id}
                onClick={() => setActiveGroupId((current) => (current === group.id ? null : group.id))}
              >
                {group.chipLabel} {group.majors.length}
              </button>
            ))}
          </div>
        ) : null}
      </div>

      {shown.map((group) => (
        <section key={group.id}>
          <div className="mb-4">
            <h3 className="text-[19px] leading-[1.4]">{group.title}</h3>
            <p className="sub mt-1.5">{group.hint}</p>
          </div>
          <ul className="flex flex-col gap-3">
            {group.majors.map((major, index) => (
              <li
                key={major.major_id}
                className="reveal"
                style={{ animationDelay: `${Math.min(index, 8) * 45}ms` }}
              >
                <MajorCard
                  major={major}
                  ordinal={index + 1}
                  onOpenDepartments={() => setOpenMajor(major)}
                  onSelectForSubjects={() =>
                    dispatch({ type: "major_selected", majorId: major.major_id })
                  }
                />
              </li>
            ))}
          </ul>
        </section>
      ))}

      <Modal
        open={openMajor !== null}
        onClose={() => setOpenMajor(null)}
        title={`${openMajor?.label ?? ""} 전공이 개설된 학과`}
        subtitle="대학알리미 공시 자료를 바탕으로 한 목록이에요. 합격 가능성을 판단하는 자료는 아니에요."
      >
        {openMajor !== null ? <DepartmentBrowser majorId={openMajor.major_id} /> : null}
      </Modal>
    </div>
  );
}

function MajorCard({
  major,
  ordinal,
  onOpenDepartments,
  onSelectForSubjects,
}: {
  major: MajorRelevance;
  ordinal: number;
  onOpenDepartments: () => void;
  onSelectForSubjects: () => void;
}) {
  return (
    <Card className="mcard">
      <div className="flex gap-4">
        <span className="rankno" aria-hidden="true">
          {ordinal}
        </span>

        <div className="min-w-0 flex-1">
          <h4 className="text-[19px] mb-1">{major.label}</h4>

          {/* 전공 소개 문장(정본 description) — 관련도 근거도, "학생에게 적합한 이유"도
              아니다. 매칭 결과 문구(아래 relevance_reason 문단)와 절대 같은 문장으로
              합치지 않는다 — 서로 다른 <p>로 분리해서 렌더링한다. */}
          <p className="sub mb-2" data-testid="major-description">
            {major.description}
          </p>

          <div className="mb-2 flex flex-wrap items-center gap-2">
            <Badge>{major.relevance_label}</Badge>
            <Badge tone="quiet">근거 {major.evidence_sufficiency}</Badge>
          </div>

          <p className="sub mb-5" data-testid="major-relevance-reason">
            {major.repeated_context_count > 0
              ? `서로 다른 ${major.repeated_context_count}개 분야의 답변에서 반복해서 나타났어요.`
              : "이번 답변에서 관련된 모습이 확인됐어요."}
          </p>

          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" size="sm" onClick={onOpenDepartments}>
              어떤 학과가 있나요?
            </Button>
            <Button size="sm" onClick={onSelectForSubjects}>
              이 전공으로 과목 추천받기
            </Button>
          </div>
        </div>
      </div>
    </Card>
  );
}
