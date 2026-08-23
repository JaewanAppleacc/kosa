/**
 * 렌더 중 예외를 잡는 마지막 그물.
 *
 * 이게 없으면 예외 하나에 React가 트리를 통째로 언마운트해서 흰 화면만 남고,
 * 학생은 새로고침 말고는 할 수 있는 게 없다. 여기서 잡아 다시 시도할 길을 준다.
 */
import { Component, type ErrorInfo, type ReactNode } from "react";
import { Button, ScreenShell, StateBlock } from "./ui";

interface Props {
  children: ReactNode;
  /** 복구 시도 시 호출. 세션을 버리고 처음부터 시작하는 등 바깥 상태를 정리한다. */
  onReset?: () => void;
}

interface State {
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    // 학생 화면에는 내부 정보를 노출하지 않는다. 개발 중 원인 추적용으로만 남긴다.
    console.error("[TRAIL] 화면을 그리는 중 오류가 발생했습니다.", error, info.componentStack);
  }

  private handleReset = (): void => {
    this.setState({ error: null });
    this.props.onReset?.();
  };

  render(): ReactNode {
    if (this.state.error === null) return this.props.children;

    return (
      <ScreenShell>
        <div className="flex min-h-[70dvh] flex-col justify-center">
          <StateBlock
            tone="error"
            title="화면을 표시하는 중 문제가 생겼어요"
            description="지금까지 답한 내용은 서버에 저장돼 있어요. 다시 시도해 주세요."
            action={
              <>
                <Button onClick={this.handleReset}>다시 시도</Button>
                <Button variant="secondary" onClick={() => window.location.reload()}>
                  새로고침
                </Button>
              </>
            }
          />
        </div>
      </ScreenShell>
    );
  }
}
