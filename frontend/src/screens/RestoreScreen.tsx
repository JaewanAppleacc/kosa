/**
 * Session 복원 — 새로고침 후 저장해둔 session_id로 이어갈지 묻는다.
 *
 * 서버 Session은 In-Memory라 서버가 재시작되면 SESSION_NOT_FOUND가 온다.
 * 이건 오류 화면이 아니라 "이어갈 수 없으니 새로 시작" 안내로 처리한다.
 */
import { restoreSession } from "@/api/endpoints";
import { isApiError } from "@/api/errors";
import { Logo } from "@/components/brand/Logo";
import { Button, Card, ScreenShell, Spinner, StateBlock } from "@/components/ui";
import { useAsync } from "@/hooks/useAsync";
import { stepFromPhase, useAppState } from "@/session/AppState";
import { clearSessionId } from "@/session/sessionStorage";

export function RestoreScreen({ sessionId, onGiveUp }: { sessionId: string; onGiveUp: () => void }) {
  const { dispatch } = useAppState();
  const restore = useAsync((signal) => restoreSession(sessionId, signal), [sessionId]);

  if (restore.status === "loading" || restore.status === "idle") {
    return (
      <ScreenShell>
        <div className="flex min-h-[60dvh] flex-col items-center justify-center gap-6">
          <Spinner label="하던 이야기를 찾는 중" />
        </div>
      </ScreenShell>
    );
  }

  if (restore.status === "error") {
    const gone = isApiError(restore.error, "SESSION_NOT_FOUND");
    return (
      <ScreenShell>
        <div className="flex min-h-[60dvh] flex-col justify-center">
          <StateBlock
            title={gone ? "이어서 할 검사가 없어요" : "이야기를 불러오지 못했어요"}
            description={
              gone
                ? "이전 기록이 남아 있지 않아요. 처음부터 다시 시작해주세요."
                : "잠시 후 다시 시도하거나 처음부터 시작해주세요."
            }
            action={
              <div className="flex flex-wrap justify-center gap-2">
                {gone ? null : (
                  <Button variant="outline" onClick={restore.reload}>
                    다시 시도
                  </Button>
                )}
                <Button
                  onClick={() => {
                    clearSessionId();
                    onGiveUp();
                  }}
                >
                  처음부터 시작
                </Button>
              </div>
            }
          />
        </div>
      </ScreenShell>
    );
  }

  const data = restore.data;
  const step = stepFromPhase(data.phase);

  return (
    <ScreenShell>
      <div className="flex min-h-[60dvh] flex-col justify-center">
        <Card>
          <div className="flex flex-col items-center gap-7 py-6 text-center">
            <Logo size={80} />
            <div>
              <h1 className="mb-2 text-[24px]">하던 이야기가 있어요</h1>
              <p className="sub">이어서 하시겠어요?</p>
            </div>
            <div className="flex flex-wrap justify-center gap-2.5">
          <Button
            onClick={() => dispatch({ type: "session_restored", sessionId: data.session_id, step })}
            disabled={step === "start"}
          >
            이어서 하기
          </Button>
          <Button
            variant="secondary"
            onClick={() => {
              clearSessionId();
              onGiveUp();
            }}
          >
            처음부터 시작
          </Button>
            </div>
            {step === "start" ? (
              <p className="mut text-[12.5px]">
                이어서 할 수 있는 지점이 없어요. 처음부터 시작해주세요.
              </p>
            ) : null}
          </div>
        </Card>
      </div>
    </ScreenShell>
  );
}
