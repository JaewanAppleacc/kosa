import { Logo, Wordmark } from "@/components/brand/Logo";
import { ErrorView } from "@/components/ErrorView";
import { Button, Spinner } from "@/components/ui";
import { createSession, fetchContextCatalog } from "@/api/endpoints";
import { useAction, useAsync } from "@/hooks/useAsync";
import { useAppState } from "@/session/AppState";

/** 초안 6b 시작 화면 — 배경 블롭 두 개, 중앙 정렬, 큰 CTA 하나. */
export function StartScreen() {
  const { dispatch } = useAppState();
  /**
   * 시작 전에 "몇 개의 이야기로 진행되는지"를 알려주려고 목록만 미리 받아둔다.
   * 실패해도 시작을 막지 않는다 — 그 칩만 빠지고 나머지는 그대로 보인다.
   */
  const catalog = useAsync((signal) => fetchContextCatalog(signal), []);
  const policy = catalog.status === "success" ? catalog.data.selection_policy : null;
  const contextCountLabel =
    policy === null
      ? null
      : policy.final_context_min_count === policy.final_context_max_count
        ? `이야기 ${policy.final_context_min_count}개로 진행`
        : `이야기 ${policy.final_context_min_count}~${policy.final_context_max_count}개로 진행`;

  const start = useAction(async () => {
    // user_id는 서버가 고정한다 — 화면은 아무것도 보내지 않는다.
    const session = await createSession();
    dispatch({ type: "session_started", sessionId: session.session_id });
    return session;
  });

  return (
    <div className="relative min-h-dvh overflow-hidden">
      <span
        className="trail-blob"
        style={{ width: 320, height: 320, background: "var(--color-accent-100)", left: -90, top: -70 }}
      />
      <span
        className="trail-blob"
        style={{
          width: 240,
          height: 240,
          background: "var(--color-accent-2-100)",
          right: -60,
          bottom: -70,
          animationDelay: "-4s",
        }}
      />

      <div className="relative z-10 grid min-h-dvh place-items-center px-6 py-14">
        <div className="max-w-[620px] text-center">
          <div className="flex flex-col items-center gap-4">
            <Logo size={104} />
            <Wordmark size="lg" showTagline />
          </div>

          <h1
            className="trail-word mt-9 mb-3.5 text-[clamp(28px,6vw,40px)] leading-[1.32]"
            style={{ letterSpacing: "-0.01em" }}
          >
            좋아하는 이야기를 따라가면
            <br />
            진로가 보이기 시작해요
          </h1>

          <p className="mx-auto mb-6 max-w-[52ch] text-[16px] leading-[1.75]" style={{ color: "var(--color-neutral-700)" }}>
            게임, 유튜브, 학교생활처럼 이미 좋아하는 이야기 안에서 질문에 답하면 돼요.
            <br className="hidden sm:inline" />
            유형으로 정해주지 않고, 지금까지 보인 모습만 보여줘요.
          </p>

          <ul className="mb-8 flex flex-wrap justify-center gap-2">
            {contextCountLabel !== null ? (
              <li>
                <span className="chip chip-quiet">📍 {contextCountLabel}</span>
              </li>
            ) : null}
            <li>
              <span className="chip chip-quiet">🔁 답에 따라 다음 질문이 달라져요</span>
            </li>
            <li>
              <span className="chip chip-quiet">📄 유형 대신 문장으로 정리</span>
            </li>
          </ul>

          {start.error ? (
            <div className="mb-6">
              <ErrorView error={start.error} onRetry={() => void start.run()} />
            </div>
          ) : null}

          <div className="flex flex-wrap items-center justify-center gap-3">
            <Button size="lg" onClick={() => void start.run()} disabled={start.pending}>
              {start.pending ? <Spinner label="시작하는 중" /> : "3분만 해볼까요 →"}
            </Button>
          </div>

          <p className="mut mt-5 text-[13px]">
            중간에 그만해도 답한 내용은 저장돼요 · 학교나 선생님에게 공유되지 않아요
          </p>
        </div>
      </div>
    </div>
  );
}
