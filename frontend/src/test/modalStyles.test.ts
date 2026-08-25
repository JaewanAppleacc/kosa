/**
 * Modal.tsx가 쓰는 클래스가 실제로 스타일시트에 정의돼 있는지 확인한다.
 *
 * 배경: Modal 컴포넌트를 도입할 때(9507823) 마크업만 들어가고 `mdl-*` CSS가
 * 한 번도 작성되지 않았다. 학과가 3~4건일 때는 스타일 없는 블록이 짧아서
 * 티가 나지 않았지만, 전국 Master 승격으로 목록이 133건이 되자
 * "서울 42개인데 카드가 1개만 보인다"로 드러났다 — 오버레이도 스크롤도 없어서
 * 목록이 문서 흐름에 그대로 펼쳐지고 뷰포트에는 맨 위만 남는다.
 *
 * jsdom은 CSS를 적용하지 않으므로 렌더 테스트로는 이 결함을 잡을 수 없다.
 * 그래서 "마크업이 참조하는 클래스에 정의가 있는가"를 직접 검사한다.
 */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const SRC = resolve(__dirname, "..");
const modalSource = readFileSync(resolve(SRC, "components/ui/Modal.tsx"), "utf8");
const styleSource = readFileSync(resolve(SRC, "styles/index.css"), "utf8");

/** Modal.tsx의 className 문자열에서 mdl-로 시작하는 클래스를 전부 뽑는다. */
function usedModalClasses(): string[] {
  const found = new Set<string>();
  for (const match of modalSource.matchAll(/className="([^"]+)"/g)) {
    for (const name of match[1].split(/\s+/)) {
      if (name.startsWith("mdl-")) found.add(name);
    }
  }
  return [...found].sort();
}

describe("Modal 스타일 계약", () => {
  it("Modal.tsx가 mdl- 클래스를 실제로 쓰고 있다", () => {
    expect(usedModalClasses().length).toBeGreaterThan(0);
  });

  it("Modal.tsx가 쓰는 모든 mdl- 클래스에 CSS 정의가 있다", () => {
    const missing = usedModalClasses().filter(
      (name) => !new RegExp(`\\.${name}\\b`).test(styleSource),
    );
    expect(missing).toEqual([]);
  });

  it("팝업 패널이 화면 높이를 넘지 않고, 본문이 스크롤된다", () => {
    // 목록이 길어져도 카드가 잘려 보이지 않으려면 이 두 가지가 반드시 필요하다.
    const panel = /\.mdl-panel\s*\{[^}]*\}/.exec(styleSource)?.[0] ?? "";
    const body = /\.mdl-body\s*\{[^}]*\}/.exec(styleSource)?.[0] ?? "";

    expect(panel).toMatch(/max-height/);
    expect(body).toMatch(/overflow-y\s*:\s*auto/);
  });

  it("배경 레이어가 화면 전체를 덮는 고정 위치다", () => {
    const root = /\.mdl-root\s*\{[^}]*\}/.exec(styleSource)?.[0] ?? "";
    expect(root).toMatch(/position\s*:\s*fixed/);
  });
});
