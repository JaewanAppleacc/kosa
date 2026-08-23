/**
 * session_id 보관 — 새로고침 후 복원에 쓴다.
 *
 * user_id는 저장하지 않는다(서버가 고정하므로 화면이 알 필요가 없다).
 * 답변 내용·Profile 같은 결과물도 저장하지 않는다 — 항상 서버에서 다시 받는다.
 */
const STORAGE_KEY = "trail.session_id";

export function loadSessionId(): string | null {
  try {
    const value = window.localStorage.getItem(STORAGE_KEY);
    return value && value.trim() ? value : null;
  } catch {
    // 사생활 보호 모드 등에서 접근이 막힐 수 있다. 복원을 포기하고 새로 시작한다.
    return null;
  }
}

export function saveSessionId(sessionId: string): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, sessionId);
  } catch {
    /* 저장 실패는 치명적이지 않다 — 이번 세션은 메모리로만 진행된다. */
  }
}

export function clearSessionId(): void {
  try {
    window.localStorage.removeItem(STORAGE_KEY);
  } catch {
    /* noop */
  }
}
