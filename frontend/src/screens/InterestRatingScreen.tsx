/**
 * 관심도 평가 — 타일 안의 5점 스케일을 한 번 눌러 바로 점수를 매긴다.
 *
 * Context 목록·개수 정책은 전부 `GET /contexts`에서 온다.
 * 점수는 반드시 JSON 정수로 보낸다 — HTML 입력값은 문자열이라 서버가 422로 거부한다.
 */
import { useEffect } from "react";
import { fetchContextCatalog, submitInterestRating } from "@/api/endpoints";
import type { ContextCatalogItem } from "@/api/endpoints";
import { ErrorView } from "@/components/ErrorView";
import { Button, Card, ProgressBar, ScreenShell, Spinner, StateBlock, TopBar } from "@/components/ui";
import { contextEmoji } from "@/domain/contextEmoji";
import { useAction, useAsync } from "@/hooks/useAsync";
import { useAppState } from "@/session/AppState";

const SCORES = [1, 2, 3, 4, 5] as const;
const SCORE_LABELS: Record<number, string> = {
  1: "관심 없어요",
  2: "조금 있어요",
  3: "보통이에요",
  4: "관심 있어요",
  5: "아주 좋아해요",
};

export function InterestRatingScreen() {
  const { state, dispatch } = useAppState();
  const catalog = useAsync((signal) => fetchContextCatalog(signal), []);

  const submit = useAction(async () => {
    if (!state.sessionId) return;
    await submitInterestRating(state.sessionId, state.ratings);
    dispatch({ type: "ratings_submitted" });
  });

  const policyLoaded = catalog.status === "success" ? catalog.data.selection_policy : null;
  useEffect(() => {
    if (policyLoaded && state.policy === null) dispatch({ type: "policy_loaded", policy: policyLoaded });
  }, [policyLoaded, state.policy, dispatch]);

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
  if (catalog.data.contexts.length === 0) {
    return (
      <Shell>
        <StateBlock title="관심 분야 목록이 비어 있어요" description="잠시 후 다시 시도해주세요." />
      </Shell>
    );
  }

  const contexts = catalog.data.contexts;
  const minimumRequired = catalog.data.selection_policy.preferred_context_min_count;
  const ratedCount = Object.keys(state.ratings).length;
  const canSubmit = ratedCount >= minimumRequired && !submit.pending;

  return (
    <Shell>
      <Card className="!p-0">
        <div className="p-6 sm:p-8">
          <h2 className="mb-1.5 text-[clamp(20px,4vw,24px)] leading-[1.35]">
            요즘 어떤 이야기에 마음이 가나요?
          </h2>
          <p className="sub">타일의 점을 눌러서 관심 가는 정도만 표시해 주세요. 잘하는 것과는 상관없어요.</p>

          <div className="my-5 flex items-center gap-3">
            <div className="flex-1">
              <ProgressBar value={ratedCount} max={contexts.length} />
            </div>
            <span className="mut flex-none text-[12.5px]" aria-live="polite">
              {contexts.length}개 중 {ratedCount}개
            </span>
          </div>

          <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
            {contexts.map((context) => (
              <li key={context.context_id}>
                <ContextTile
                  context={context}
                  score={state.ratings[context.context_id]}
                  onScore={(score) =>
                    dispatch({ type: "rating_changed", contextId: context.context_id, score })
                  }
                />
              </li>
            ))}
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
            <p className="mut flex-1 text-[12.5px]">
              {canSubmit ? "언제든 다시 바꿀 수 있어요." : `${minimumRequired}개 이상 표시해 주세요.`}
            </p>
            <Button onClick={() => void submit.run()} disabled={!canSubmit}>
              {submit.pending ? <Spinner label="저장하는 중" /> : "다음 →"}
            </Button>
          </div>
        </div>
      </Card>
    </Shell>
  );
}

/** 타일 하나 = 이모지 + 이름 + 바로 누를 수 있는 5점 스케일. */
function ContextTile({
  context,
  score,
  onScore,
}: {
  context: ContextCatalogItem;
  score: number | undefined;
  onScore: (score: number) => void;
}) {
  return (
    <div className={`tile ${score !== undefined ? "on" : ""}`} title={context.interest_rating_prompt}>
      <em aria-hidden="true">{contextEmoji(context.context_id)}</em>
      <span className="leading-tight">{context.label}</span>

      <div className="scale" role="group" aria-label={`${context.label} 관심도`}>
        {SCORES.map((value) => (
          <button
            key={value}
            type="button"
            className={score !== undefined && value <= score ? "on" : undefined}
            aria-pressed={score === value}
            aria-label={`${context.label} — ${SCORE_LABELS[value]}`}
            onClick={() => onScore(value)}
          >
            <span aria-hidden="true" />
          </button>
        ))}
      </div>

      <span className="mut h-4 text-[11px] leading-4">
        {score !== undefined ? SCORE_LABELS[score] : ""}
      </span>
    </div>
  );
}

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <>
      <TopBar right={<span className="mut text-[12.5px]">자동 저장됨</span>} />
      <ScreenShell wide title="관심 있는 이야기 표시하기">{children}</ScreenShell>
    </>
  );
}
