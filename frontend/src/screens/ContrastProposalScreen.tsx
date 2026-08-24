/**
 * Contrast Context 제안 — 초안 6d 제안 모달.
 *
 * 최종 Context 개수는 selection_policy의 final_context_min_count~max_count 범위다.
 * 제안을 받아들이면 고른 것 + 대비 1개, 받아들이지 않으면 고른 것만으로 확정한다 —
 * 둘 다 서버가 허용하는 범위다. 개수를 화면에 숫자로 박지 않는다: Vertical Slice(2+1)와
 * 전체 모드(4+1)에서 값이 달라지고, 그 값은 GET /contexts가 알려준다.
 * coverage_replacement_enabled가 false면 교체 UI를 아예 숨긴다.
 */
import { confirmContexts, fetchContextCatalog } from "@/api/endpoints";
import { ErrorView } from "@/components/ErrorView";
import { Button, Card, ScreenShell, Spinner, TopBar } from "@/components/ui";
import { contextEmoji } from "@/domain/contextEmoji";
import { useAction, useAsync } from "@/hooks/useAsync";
import { useAppState } from "@/session/AppState";

export function ContrastProposalScreen() {
  const { state, dispatch } = useAppState();
  const catalog = useAsync((signal) => fetchContextCatalog(signal), []);

  const confirm = useAction(async (includeContrast: boolean) => {
    if (!state.sessionId || !state.contrast) return;
    const finalIds = includeContrast
      ? [...state.preferredContextIds, state.contrast.contrast_context_id]
      : [...state.preferredContextIds];
    const response = await confirmContexts(state.sessionId, finalIds);
    dispatch({ type: "contexts_confirmed", finalContextIds: response.final_context_ids });
  });

  if (!state.contrast) {
    return (
      <Shell>
        <ErrorView error={new Error("제안 정보를 찾을 수 없습니다.")} />
      </Shell>
    );
  }

  const labelOf = (contextId: string) => {
    if (catalog.status !== "success") return contextId;
    return catalog.data.contexts.find((c) => c.context_id === contextId)?.label ?? contextId;
  };

  const contrastId = state.contrast.contrast_context_id;
  const policy = catalog.status === "success" ? catalog.data.selection_policy : null;
  const replacements =
    policy?.coverage_replacement_enabled === false ? [] : state.contrast.coverage_replacement_offered;
  const canSkipContrast =
    policy === null || state.preferredContextIds.length >= policy.final_context_min_count;

  return (
    <Shell>
      <Card>
        <span className="chip chip-blush mb-4">한 가지만 더 제안할게요</span>

        <h2 className="mb-2 text-[clamp(21px,4vw,26px)] leading-[1.4]">
          {labelOf(contrastId)} 이야기도 함께 볼까요?
        </h2>
        <p className="sub mb-6">
          고른 것과 결이 다른 이야기를 하나 더 보면, 한쪽으로 치우치지 않은 결과를 볼 수 있어요.
        </p>

        <div
          className="mb-6 flex items-start gap-4 rounded-[18px] p-5"
          style={{ background: "var(--color-accent-100)" }}
        >
          <span className="text-[30px] leading-none" aria-hidden="true">
            {contextEmoji(contrastId)}
          </span>
          <p className="text-[14.5px] leading-[1.7]" style={{ color: "var(--color-accent-900)" }}>
            {state.contrast.contrast_reason}
          </p>
        </div>

        <p className="gsec">이번에 살펴볼 이야기</p>
        <ul className="mb-6 flex flex-wrap gap-2">
          {[...state.preferredContextIds, contrastId].map((id) => (
            <li key={id}>
              <span className={id === contrastId ? "chip" : "chip chip-quiet"}>
                <span aria-hidden="true">{contextEmoji(id)}</span>
                {labelOf(id)}
              </span>
            </li>
          ))}
        </ul>

        {replacements.length > 0 ? (
          <div className="mb-6">
            <p className="gsec mb-2">이렇게 바꿔볼 수도 있어요</p>
            <div className="flex flex-wrap gap-2">
              {replacements.map((id) => (
                <Button
                  key={id}
                  variant="outline"
                  size="sm"
                  onClick={() => dispatch({ type: "contrast_replaced", contextId: id })}
                >
                  {contextEmoji(id)} {labelOf(id)}(으)로 교체
                </Button>
              ))}
            </div>
          </div>
        ) : null}

        {confirm.error ? (
          <div className="mb-5">
            <ErrorView error={confirm.error} onRetry={() => confirm.reset()} />
          </div>
        ) : null}

        {/* 개수는 항상 선택한 선호 Context 수(state.preferredContextIds.length)에서 그대로
            계산한다 — 4/5를 상수로 박지 않는다. Flag OFF(2+1)에서는 "총 3개/2개"로,
            Flag ON(4+1)에서는 "총 5개/4개"로 자동으로 달라진다. */}
        <p className="mut mb-3 text-[12.5px]">
          이 제안은 꼭 받아들이지 않아도 괜찮아요 — 수락하면 총 {state.preferredContextIds.length + 1}개,
          거절하면 {state.preferredContextIds.length}개로 시작해요.
        </p>

        <div className="flex flex-wrap items-center gap-3">
          <Button onClick={() => void confirm.run(true)} disabled={confirm.pending}>
            {confirm.pending ? <Spinner label="준비하는 중" /> : "좋아요, 시작할게요 →"}
          </Button>
          {canSkipContrast ? (
            <Button variant="secondary" onClick={() => void confirm.run(false)} disabled={confirm.pending}>
              고른 것만으로 시작
            </Button>
          ) : null}
        </div>
      </Card>
    </Shell>
  );
}

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <>
      <TopBar right={<span className="mut text-[12.5px]">자동 저장됨</span>} />
      <ScreenShell>{children}</ScreenShell>
    </>
  );
}
