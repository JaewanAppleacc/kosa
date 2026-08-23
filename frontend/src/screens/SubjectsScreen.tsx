/**
 * 고교학점제 과목 추천.
 *
 * source로 단계를 구분한다:
 * - PRE_SURVEY   : 개설 여부 미확정(is_actually_offered === null). "핵심 과목"이 아니라
 *                  "우선 희망 과목"으로 표현한다.
 * - POST_OFFERING: 학교가 실제로 여는 과목 확정 후. 미개설 과목은 unavailable_subjects로
 *                  분리되고, 대체 과목은 category="alternative"로 온다.
 */
import { useState } from "react";
import { fetchSubjects } from "@/api/endpoints";
import type { CourseProfile, CourseRecommendationItem } from "@/api/contracts";
import { ErrorView } from "@/components/ErrorView";
import { Badge, Button, Card, SectionTitle, Spinner, StateBlock } from "@/components/ui";
import { useAsync } from "@/hooks/useAsync";
import { useAppState } from "@/session/AppState";
import { CourseUploadPanel } from "./CourseUploadPanel";

export function SubjectsScreen() {
  const { state, dispatch } = useAppState();
  const [reloadKey, setReloadKey] = useState(0);

  const subjects = useAsync(
    (signal) => {
      if (!state.sessionId || !state.selectedMajorId) {
        return Promise.reject(new Error("전공이 선택되지 않았습니다."));
      }
      return fetchSubjects(state.sessionId, state.selectedMajorId, signal);
    },
    [state.sessionId, state.selectedMajorId, reloadKey],
    { enabled: Boolean(state.sessionId && state.selectedMajorId) },
  );

  // 전공을 고르는 건 학생의 명시적 행동이다 — 화면이 임의로 정하지 않는다.
  if (!state.selectedMajorId) {
    return (
      <StateBlock
        title="어떤 전공으로 과목을 볼까요?"
        description="전공 탭에서 '이 전공으로 과목 추천받기'를 눌러주세요."
        action={
          <Button variant="outline" onClick={() => dispatch({ type: "result_tab_changed", tab: "majors" })}>
            전공 보러 가기
          </Button>
        }
      />
    );
  }

  if (subjects.status === "loading" || subjects.status === "idle") {
    return (
      <div className="py-16 text-center">
        <Spinner label="과목을 살펴보는 중" />
      </div>
    );
  }
  if (subjects.status === "error") return <ErrorView error={subjects.error} onRetry={subjects.reload} />;

  const data = subjects.data;
  const isPreSurvey = data.source === "PRE_SURVEY";

  return (
    <div className="space-y-8">
      <RecommendationSection profile={data} />

      {data.unavailable_subjects.length > 0 ? (
        <section>
          <SectionTitle hint="희망 과목이었지만 우리 학교에서는 열리지 않아요.">
            이번에 들을 수 없는 과목
          </SectionTitle>
          <ul className="space-y-2">
            {data.unavailable_subjects.map((subject) => (
              <li key={subject.subject_id} className="rounded-2xl p-4" style={{ background: "var(--color-neutral-100)" }}>
                <p className="font-semibold">{subject.label}</p>
                <p className="mut mt-1 text-[13.5px] leading-relaxed">{subject.reason}</p>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {data.unresolved_candidates.length > 0 ? (
        <section>
          <SectionTitle hint="편제표에서 어떤 과목인지 확인하지 못한 값이에요.">
            확인이 필요한 과목
          </SectionTitle>
          <ul className="space-y-2">
            {data.unresolved_candidates.map((candidate, index) => (
              <li
                key={`${candidate.raw_text}-${index}`}
                className="mut rounded-2xl bg-white p-3.5 text-[13.5px]" style={{ boxShadow: "inset 0 0 0 1.5px var(--line)" }}
              >
                {candidate.raw_text}
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {isPreSurvey ? (
        <CourseUploadPanel onConfirmed={() => setReloadKey((n) => n + 1)} />
      ) : (
        <p className="chip">
          학교 편제표를 반영한 최종 추천이에요.
        </p>
      )}
    </div>
  );
}

function RecommendationSection({ profile }: { profile: CourseProfile }) {
  const isPreSurvey = profile.source === "PRE_SURVEY";
  const core = profile.recommendations.filter((r) => r.category === "core");
  const explore = profile.recommendations.filter((r) => r.category === "explore");
  const alternative = profile.recommendations.filter((r) => r.category === "alternative");

  if (profile.recommendations.length === 0) {
    return (
      <StateBlock
        title="추천할 과목을 찾지 못했어요"
        description={
          isPreSurvey
            ? "질문에 조금 더 답하면 연결되는 과목을 찾아볼 수 있어요."
            : "확정한 개설과목 중에서는 연결되는 과목을 찾지 못했어요."
        }
      />
    );
  }

  return (
    <div className="space-y-8">
      {core.length > 0 ? (
        <section>
          <SectionTitle
            hint={
              isPreSurvey
                ? "답변 근거가 뚜렷해서 먼저 살펴보면 좋을 과목이에요. 학교 개설 여부는 아직 확인 전이에요."
                : "학교에서 실제로 열리는 것을 확인한 과목이에요."
            }
          >
            {isPreSurvey ? "우선 희망 과목" : "핵심 과목"}
          </SectionTitle>
          <SubjectList items={core} />
        </section>
      ) : null}

      {alternative.length > 0 ? (
        <section>
          <SectionTitle hint="원래 희망했던 과목 대신 들을 수 있는 과목이에요.">대체 과목</SectionTitle>
          <SubjectList items={alternative} />
        </section>
      ) : null}

      {explore.length > 0 ? (
        <section>
          <SectionTitle hint="관심이 이어진다면 함께 살펴보면 좋아요.">함께 살펴볼 과목</SectionTitle>
          <SubjectList items={explore} />
        </section>
      ) : null}
    </div>
  );
}

function SubjectList({ items }: { items: CourseRecommendationItem[] }) {
  return (
    <ul className="space-y-3">
      {items.map((item) => (
        <li key={item.subject_id}>
          <Card>
            <div className="mb-2 flex flex-wrap items-center gap-2">
              <h3 className="text-[17px]">{item.label}</h3>
              {/* null(미확정)을 "미개설"로 표현하면 거짓 정보가 된다 — 세 상태를 구분한다. */}
              {item.is_actually_offered === true ? <Badge>우리 학교 개설</Badge> : null}
              {item.is_actually_offered === null ? <Badge tone="quiet">개설 여부 확인 전</Badge> : null}
            </div>
            <p className="sub">{item.reason}</p>
          </Card>
        </li>
      ))}
    </ul>
  );
}
