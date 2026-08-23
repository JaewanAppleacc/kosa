import "@testing-library/jest-dom/vitest";

// Node(22+, 확인은 26에서)가 실험적으로 전역 localStorage/sessionStorage를 자체
// 정의하면서, jsdom이 준비한 실제 구현이 vitest의 populateGlobal()에서 "이미
// global에 있는 키"로 취급돼 덮어써지지 못한다(2026-08-24, 프론트 통합 중 발견).
// Node의 버전은 --localstorage-file 없이는 undefined만 반환해 모든 스토리지
// 접근이 깨진다. jsdom window가 가진 실제 구현으로 다시 연결한다.
const jsdomInstance = (globalThis as unknown as { jsdom?: { window: Window } }).jsdom;
if (jsdomInstance) {
  Object.defineProperty(globalThis, "localStorage", {
    get: () => jsdomInstance.window.localStorage,
    configurable: true,
  });
  Object.defineProperty(globalThis, "sessionStorage", {
    get: () => jsdomInstance.window.sessionStorage,
    configurable: true,
  });
}
