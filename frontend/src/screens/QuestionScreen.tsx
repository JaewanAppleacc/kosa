/**
 * 질문 화면 — 초안 6e. Context 칩 + 진행 바 + A~E 선택지 + 오른쪽 "내 영역" 레일.
 *
 * 지켜야 할 것:
 * - 진행 바는 **Context 진행도**만 나타낸다. 질문 수는 답변에 따라 달라져서 비율이
 *   성립하지 않는다(A 확인) — 질문은 "N번째 질문"이라는 서수 문구로만 표시한다.
 * - CONTEXT_EARLY_TERMINATED면 question이 null이다 — 질문 Component를 그리지 않는다.
 * - 답변 중복 제출은 useAction이 구조적으로 막는다.
 * - primary_trait_delta·target_traits 같은 내부 값은 절대 화면에 노출하지 않는다.
 */
import { useCallback, useEffect, useState } from "react";
import { fetchContextCatalog, fetchNextQuestion, submitAnswer } from "@/api/endpoints";
import type { NextQuestionResponse, QuestionDeliveryStatus } from "@/api/contracts";
import { ErrorView } from "@/components/ErrorView";
import { Button, Card, ProgressBar, ScreenShell, Spinner, TopBar } from "@/components/ui";
import { contextEmoji } from "@/domain/contextEmoji";
import { useAction, useAsync } from "@/hooks/useAsync";
import { useAppState } from "@/session/AppState";

/** 상태별 안내 문구. 학생에게 내부 Fallback 용어를 그대로 쓰지 않는다. */
const STATUS_NOTE: Partial<Record<QuestionDeliveryStatus, string>> = {
  REGENERATING: "질문을 다시 다듬고 있어요.",
  CACHE_USED: "미리 준비해둔 질문이에요.",
  BACKUP_USED: "미리 준비해둔 질문이에요.",
};

const ORDINALS = ["첫", "두", "세", "네", "다섯", "여섯", "일곱", "여덟", "아홉", "열"];

function ordinal(index: number): string {
  return ORDINALS[index] ? `${ORDINALS[index]} 번째 질문` : `${index + 1}번째 질문`;
}

export function QuestionScreen() {
  const { state, dispatch } = useAppState();
  const [answeredTotal, setAnsweredTotal] = useState(0);
  const [pendingReload, setPendingReload] = useState(0);

  const catalog = useAsync((signal) => fetchContextCatalog(signal), []);
  const question = useAsync<NextQuestionResponse>(
    (signal) => {
      if (!state.sessionId) return Promise.reject(new Error("세션이 없습니다."));
      return fetchNextQuestion(state.sessionId, signal);
    },
    [state.sessionId, pendingReload],
  );

  const labelOf = useCallback(
    (contextId: string | null) => {
      if (!contextId) return "";
      if (catalog.status !== "success") return contextId;
      return catalog.data.contexts.find((c) => c.context_id === contextId)?.label ?? contextId;
    },
    [catalog],
  );

  const answer = useAction(async (questionId: string, optionId: string) => {
    if (!state.sessionId) return;
    const result = await submitAnswer(state.sessionId, questionId, optionId);
    setAnsweredTotal((n) => n + 1);
    if (result.next_action === "ASSESSMENT_COMPLETE") {
      dispatch({ type: "assessment_completed" });
    } else {
      setPendingReload((n) => n + 1);
    }
  });

  const completedWithoutQuestion =
    question.status === "success" && question.data.question === null && question.data.assessment_complete;
  useEffect(() => {
    if (completedWithoutQuestion) dispatch({ type: "assessment_completed" });
  }, [completedWithoutQuestion, dispatch]);

  const currentContextId =
    question.status === "success" ? question.data.current_context_id : null;

  // 복원한 세션은 확정 목록을 모른다 — 그때는 지금까지 마주친 Context로 레일을 채운다.
  useEffect(() => {
    if (currentContextId) dispatch({ type: "context_observed", contextId: currentContextId });
  }, [currentContextId, dispatch]);

  const railContextIds =
    state.finalContextIds.length > 0 ? state.finalContextIds : state.observedContextIds;
  const contextIndex = currentContextId ? railContextIds.indexOf(currentContextId) : -1;
  /**
   * 전체 Context 개수를 아는 경우에만 진행 바를 그린다. 복원한 세션에서 관찰된 개수를
   * 분모로 쓰면 "항상 마지막 단계"처럼 보여서 거짓말이 된다.
   */
  const knowsTotalContexts = state.finalContextIds.length > 0;

  const rail = (
    <ContextRail
      contextIds={railContextIds}
      currentContextId={currentContextId}
      labelOf={labelOf}
    />
  );

  if (question.status === "loading" || question.status === "idle") {
    return (
      <Shell rail={rail}>
        <Card>
          <div className="grid place-items-center py-24">
            <Spinner label="다음 질문을 준비하는 중" />
          </div>
        </Card>
      </Shell>
    );
  }

  if (question.status === "error") {
    return (
      <Shell rail={rail}>
        <Card>
          <ErrorView error={question.error} onRetry={question.reload} />
        </Card>
      </Shell>
    );
  }

  const data = question.data;

  if (data.question === null) {
    // CONTEXT_EARLY_TERMINATED — 질문을 그리지 않고 다음 단계 안내만 한다.
    return (
      <Shell rail={rail}>
        <Card>
          <div className="py-10 text-center">
            <h2 className="mb-2 text-[20px]">이 이야기는 여기까지 살펴봤어요</h2>
            <p className="sub mx-auto mb-6">다음 이야기로 넘어갈게요.</p>
            <Button onClick={() => setPendingReload((n) => n + 1)}>계속하기 →</Button>
          </div>
        </Card>
      </Shell>
    );
  }

  const note = STATUS_NOTE[data.status];
  const current = data.question;

  return (
    <Shell rail={rail}>
      <Card>
        <div className="mb-4 flex flex-wrap items-center gap-3">
          <span className="chip">
            <span aria-hidden="true" className="text-[16px]">
              {contextEmoji(currentContextId ?? "")}
            </span>
            {labelOf(currentContextId)}
          </span>
          <span className="mut text-[13px]">
            {ordinal(data.questions_asked_in_current_context)}
            {data.questions_asked_in_current_context > 0 ? " · 앞의 답에서 이어진 질문이에요" : ""}
          </span>
          {/* A 확인(2026-08-30): 퍼센트 대신 "완료한 질문 개수"만 보여준다. */}
          <span className="mut ml-auto text-[13px]" aria-live="polite">
            {answeredTotal}개 답변함
          </span>
        </div>

        {/*
          Context 진행도만 채운다 — 질문 수 비율이 아니다.
          현재 Context 자신도 진행 중이라는 뜻으로 절반만 더한다.
        */}
        {knowsTotalContexts ? (
          <div className="mb-6">
            <ProgressBar
              value={contextIndex >= 0 ? contextIndex + 0.5 : 0}
              max={state.finalContextIds.length}
            />
          </div>
        ) : null}

        {note ? (
          <p className="mut mb-4 text-[12.5px]" aria-live="polite">
            {note}
          </p>
        ) : null}

        <h2 className="mb-2 max-w-[42ch] text-[clamp(19px,3.6vw,26px)] leading-[1.45]">
          {current.question_text}
        </h2>
        <p className="sub mb-6">가장 가까운 하나만 고르면 돼요. 맞고 틀림은 없어요.</p>

        <fieldset disabled={answer.pending} className="max-w-[800px]">
          <legend className="sr-only">{current.question_text}</legend>
          <ul className="flex flex-col gap-2.5" aria-label="답변 선택지">
            {current.options.map((option, index) => (
              <li key={option.option_id}>
                <button
                  type="button"
                  className="popt"
                  onClick={() => void answer.run(current.question_id, option.option_id)}
                  disabled={answer.pending}
                >
                  <b aria-hidden="true">{String.fromCharCode(65 + index)}</b>
                  <span>{option.text}</span>
                </button>
              </li>
            ))}
          </ul>
        </fieldset>

        <div className="mt-6 flex flex-wrap items-center gap-3">
          <p className="mut flex-1 text-[12.5px]">고른 답은 특성을 관찰하는 데만 쓰여요.</p>
          {answer.pending ? <Spinner label="답변을 반영하는 중" /> : null}
        </div>

        {answer.error ? (
          <div className="mt-5">
            <ErrorView error={answer.error} onRetry={() => answer.reset()} />
          </div>
        ) : null}
      </Card>
    </Shell>
  );
}

/** 초안 6e 오른쪽 레일 "내 영역" — 어디까지 왔는지 이야기 단위로 보여준다. */
function ContextRail({
  contextIds,
  currentContextId,
  labelOf,
}: {
  contextIds: string[];
  currentContextId: string | null;
  labelOf: (id: string | null) => string;
}) {
  if (contextIds.length === 0) return null;
  const currentIndex = currentContextId ? contextIds.indexOf(currentContextId) : -1;

  return (
    <Card>
      <p className="gsec mb-3.5">내 이야기</p>
      <ul className="flex flex-col gap-3 text-[14px]">
        {contextIds.map((id, index) => {
          const isCurrent = id === currentContextId;
          const isDone = currentIndex >= 0 && index < currentIndex;
          return (
            <li key={id} className="flex items-center gap-2.5" style={isCurrent ? undefined : { color: "var(--color-neutral-600)" }}>
              <span
                aria-hidden="true"
                className="text-[17px]"
                style={isCurrent ? undefined : { filter: "grayscale(1)", opacity: 0.6 }}
              >
                {contextEmoji(id)}
              </span>
              {labelOf(id)}
              {isCurrent ? <span className="mut text-[12px]">진행 중</span> : null}
              {isDone ? <span className="mut text-[12px]">완료</span> : null}
            </li>
          );
        })}
      </ul>
    </Card>
  );
}

function Shell({ children, rail }: { children: React.ReactNode; rail?: React.ReactNode }) {
  return (
    <>
      <TopBar right={<span className="mut text-[12.5px]">자동 저장됨</span>} />
      <ScreenShell wide>
        <div className="flex flex-col gap-6 lg:flex-row lg:items-start">
          <div className="min-w-0 flex-1">{children}</div>
          {rail ? <div className="w-full lg:w-[280px] lg:flex-none">{rail}</div> : null}
        </div>
      </ScreenShell>
    </>
  );
}
