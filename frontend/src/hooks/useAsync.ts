import { useCallback, useEffect, useRef, useState } from "react";

export type AsyncState<T> =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "success"; data: T }
  | { status: "error"; error: unknown };

/**
 * 비동기 조회의 4상태(idle/loading/success/error)를 한 곳에서 다룬다.
 * 화면이 `if (loading)` 하나로 뭉뚱그리지 않고 정상/빈 결과/오류를 구분하도록 강제한다.
 */
export function useAsync<T>(
  fn: (signal: AbortSignal) => Promise<T>,
  deps: readonly unknown[],
  options: { enabled?: boolean } = {},
): AsyncState<T> & { reload: () => void } {
  const enabled = options.enabled ?? true;
  const [state, setState] = useState<AsyncState<T>>({ status: "idle" });
  const [nonce, setNonce] = useState(0);
  const fnRef = useRef(fn);
  fnRef.current = fn;

  useEffect(() => {
    if (!enabled) {
      setState({ status: "idle" });
      return;
    }
    const controller = new AbortController();
    setState({ status: "loading" });
    fnRef
      .current(controller.signal)
      .then((data) => {
        if (!controller.signal.aborted) setState({ status: "success", data });
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        if (error instanceof DOMException && error.name === "AbortError") return;
        setState({ status: "error", error });
      });
    return () => controller.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, nonce, ...deps]);

  const reload = useCallback(() => setNonce((n) => n + 1), []);
  return { ...state, reload };
}

/**
 * 사용자의 명시적 동작(제출·확정)에 쓴다. useAsync와 달리 자동 실행되지 않고,
 * 실행 중 재호출을 막아 중복 제출을 구조적으로 차단한다.
 */
export function useAction<Args extends unknown[], T>(
  fn: (...args: Args) => Promise<T>,
): {
  run: (...args: Args) => Promise<T | undefined>;
  pending: boolean;
  error: unknown;
  reset: () => void;
} {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const pendingRef = useRef(false);
  const fnRef = useRef(fn);
  fnRef.current = fn;

  const run = useCallback(async (...args: Args) => {
    if (pendingRef.current) return undefined; // 중복 제출 방지
    pendingRef.current = true;
    setPending(true);
    setError(null);
    try {
      return await fnRef.current(...args);
    } catch (caught) {
      setError(caught);
      return undefined;
    } finally {
      pendingRef.current = false;
      setPending(false);
    }
  }, []);

  const reset = useCallback(() => setError(null), []);
  return { run, pending, error, reset };
}
