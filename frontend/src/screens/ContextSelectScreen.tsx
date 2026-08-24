/**
 * 선호 Context 선택 — 초안 6c의 타일을 그대로 쓰되 "고르기" 모드다.
 *
 * 15개를 모두 보여주되, 서버가 실제로 받아주는 것만 고를 수 있게 한다.
 * 서버는 (a) 질문 흐름을 지원하고(assessment_supported) (b) 이미 관심도를 매긴
 * Context만 선호 Context로 받는다 — 둘 중 하나라도 아니면 422다. 고른 뒤에 거절당하면
 * 학생은 이유를 알 수 없으므로, 고르기 전에 왜 못 고르는지 타일에 표시한다.
 */
import { fetchContextCatalog, selectContexts } from "@/api/endpoints";
import { ErrorView } from "@/components/ErrorView";
import { Button, Card, ScreenShell, Spinner, StateBlock, TopBar } from "@/components/ui";
import { contextEmoji } from "@/domain/contextEmoji";
import { useAction, useAsync } from "@/hooks/useAsync";
import { useAppState } from "@/session/AppState";

export function ContextSelectScreen() {
  const { state, dispatch } = useAppState();
  const catalog = useAsync((signal) => fetchContextCatalog(signal), []);

  const submit = useAction(async () => {
    if (!state.sessionId) return;
    const contrast = await selectContexts(state.sessionId, state.preferredContextIds);
    dispatch({ type: "contexts_selected", contrast });
  });

  if (catalog.status === "loading" || catalog.status === "idle") {
    return (
      <Shell>
        <div className="grid place-items-center py-24">
          <Spinner label="관심 분야를 불러오는 중" />
        </div>
      </Shell>
    );
  }
  if (catalog.status === "error") {
    return (
      <Shell>
        <ErrorView error={catalog.error} onRetry={catalog.reload} />
      </Shell>
    );
  }

  const policy = catalog.data.selection_policy;
  const minCount = policy.preferred_context_min_count;
  const maxCount = policy.preferred_context_max_count;
  const selectedCount = state.preferredContextIds.length;
  const canSubmit = selectedCount >= minCount && selectedCount <= maxCount && !submit.pending;

  // 서버가 실제로 받아주는 조건과 같은 기준으로 미리 막는다.
  const selectableReason = (contextId: string, assessmentSupported: boolean): string | null => {
    if (!assessmentSupported) return "곧 열려요";
    if (state.ratings[contextId] === undefined) return "관심도 먼저";
    return null;
  };
  const selectableCount = catalog.data.contexts.filter(
    (c) => selectableReason(c.context_id, c.assessment_supported) === null,
  ).length;

  if (selectableCount === 0) {
    return (
      <Shell>
        <StateBlock
          title="지금 고를 수 있는 이야기가 없어요"
          description="관심도를 매긴 이야기 중에 아직 질문이 준비된 것이 없어요. 앞으로 돌아가 다시 표시해 주세요."
          action={
            <Button variant="outline" onClick={() => dispatch({ type: "go_to", step: "interest_rating" })}>
              관심도 다시 표시하기
            </Button>
          }
        />
      </Shell>
    );
  }

  return (
    <Shell>
      <Card className="!p-0">
        <div className="p-6 sm:p-8">
          <h2 className="mb-1.5 text-[clamp(20px,4vw,24px)] leading-[1.35]">
            어떤 이야기부터 살펴볼까요?
          </h2>
          <p className="sub mb-5">
            {minCount === maxCount
              ? `가장 마음이 가는 ${minCount}개를 골라주세요. 나머지 하나는 제가 제안할게요.`
              : `${minCount}~${maxCount}개를 골라주세요. 하나는 제가 더 제안할게요.`}
          </p>

          <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
            {catalog.data.contexts.map((context) => {
              const selected = state.preferredContextIds.includes(context.context_id);
              const reason = selectableReason(context.context_id, context.assessment_supported);
              return (
                <li key={context.context_id}>
                  <button
                    type="button"
                    disabled={reason !== null}
                    aria-pressed={selected}
                    className={`tile ${selected ? "on" : ""}`}
                    onClick={() =>
                      dispatch({ type: "preferred_toggled", contextId: context.context_id, max: maxCount })
                    }
                  >
                    <em aria-hidden="true">{contextEmoji(context.context_id)}</em>
                    <span className="leading-tight">{context.label}</span>
                    {reason ? <span className="mut text-[10.5px]">{reason}</span> : null}
                  </button>
                </li>
              );
            })}
          </ul>
        </div>

        <div
          className="sticky bottom-0 rounded-b-[24px] border-t px-6 py-4 sm:px-8"
          style={{ borderColor: "var(--line)", background: "rgba(255,255,255,0.96)", backdropFilter: "blur(6px)" }}
        >
          {submit.error ? (
            <div className="mb-4">
              <ErrorView error={submit.error} onRetry={() => void submit.run()} />
            </div>
          ) : null}
          <div className="flex flex-wrap items-center gap-3">
            <p className="mut flex-1 text-[12.5px]" aria-live="polite">
              {selectedCount} / {maxCount} 선택함
            </p>
            <Button onClick={() => void submit.run()} disabled={!canSubmit}>
              {submit.pending ? <Spinner label="살펴보는 중" /> : "다음 →"}
            </Button>
          </div>
        </div>
      </Card>
    </Shell>
  );
}

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <>
      <TopBar right={<span className="mut text-[12.5px]">자동 저장됨</span>} />
      <ScreenShell wide title="살펴볼 이야기 고르기">{children}</ScreenShell>
    </>
  );
}
