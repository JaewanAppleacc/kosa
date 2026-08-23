/**
 * 선호 Context 선택 — 초안 6c의 타일을 그대로 쓰되 "고르기" 모드다.
 *
 * 15개를 모두 같은 모습으로 보여주고 전부 고를 수 있게 한다. 화면에서 미리 막지 않는
 * 이유는 지원 Context가 늘어나는 중이고("준비 중" 같은 과도기 표시를 남기지 않는다),
 * 실제 허용 범위는 서버가 판단하기 때문이다 — 받아줄 수 없는 조합이면 422가 오고
 * ErrorView가 그대로 안내한다.
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

  if (catalog.data.contexts.length === 0) {
    return (
      <Shell>
        <StateBlock
          title="지금 선택할 수 있는 관심 분야가 없어요"
          description="잠시 후 다시 시도해주세요."
          action={
            <Button variant="outline" onClick={() => dispatch({ type: "go_to", step: "interest_rating" })}>
              관심도 다시 평가하기
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
              return (
                <li key={context.context_id}>
                  <button
                    type="button"
                    aria-pressed={selected}
                    className={`tile ${selected ? "on" : ""}`}
                    onClick={() =>
                      dispatch({ type: "preferred_toggled", contextId: context.context_id, max: maxCount })
                    }
                  >
                    <em aria-hidden="true">{contextEmoji(context.context_id)}</em>
                    <span className="leading-tight">{context.label}</span>
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
      <ScreenShell wide>{children}</ScreenShell>
    </>
  );
}
