/**
 * 접근성 모달 — "어떤 학과가 있나요?"처럼 목록이 길어질 수 있는 내용을 화면 흐름을
 * 밀어내지 않고 띄운다.
 *
 * 지켜야 할 것:
 * · Esc / 배경 클릭 / 닫기 버튼 — 닫는 방법을 세 가지 다 둔다.
 * · 열릴 때 패널로 포커스를 옮기고, 닫을 때 원래 누른 버튼으로 되돌린다.
 * · 열려 있는 동안 뒤 배경은 스크롤되지 않는다.
 * · prefers-reduced-motion이면 등장 애니메이션을 끈다(전역 CSS에서 처리).
 */
import { useCallback, useEffect, useId, useRef, type ReactNode } from "react";
import { createPortal } from "react-dom";

const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

export function Modal({
  open,
  onClose,
  title,
  subtitle,
  toolbar,
  children,
  footer,
}: {
  open: boolean;
  onClose: () => void;
  title: ReactNode;
  subtitle?: ReactNode;
  /** 제목 아래 고정 영역(검색·필터). 본문만 스크롤되고 이 영역은 남는다. */
  toolbar?: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
}) {
  const titleId = useId();
  const panelRef = useRef<HTMLDivElement>(null);
  const openerRef = useRef<Element | null>(null);

  // 포커스를 패널 안에 가둔다 — Tab이 뒤쪽 배경 요소로 새어 나가지 않게 한다.
  const trapFocus = useCallback((event: KeyboardEvent) => {
    const panel = panelRef.current;
    if (!panel || event.key !== "Tab") return;
    const targets = Array.from(panel.querySelectorAll<HTMLElement>(FOCUSABLE)).filter(
      (element) => element.offsetParent !== null || element === document.activeElement,
    );
    if (targets.length === 0) {
      event.preventDefault();
      panel.focus();
      return;
    }
    const first = targets[0]!;
    const last = targets[targets.length - 1]!;
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }, []);

  useEffect(() => {
    if (!open) return;

    openerRef.current = document.activeElement;
    panelRef.current?.focus();

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.stopPropagation();
        onClose();
        return;
      }
      trapFocus(event);
    };
    document.addEventListener("keydown", onKeyDown, true);

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    return () => {
      document.removeEventListener("keydown", onKeyDown, true);
      document.body.style.overflow = previousOverflow;
      // 모달을 연 버튼이 아직 화면에 있으면 그 자리로 포커스를 돌려준다.
      const opener = openerRef.current;
      if (opener instanceof HTMLElement && document.contains(opener)) opener.focus();
    };
  }, [open, onClose, trapFocus]);

  if (!open) return null;

  return createPortal(
    <div className="mdl-root">
      {/* 배경: 클릭하면 닫힌다. 스크린리더에는 패널만 노출한다. */}
      <div className="mdl-back" onClick={onClose} aria-hidden="true" />
      <div
        ref={panelRef}
        className="mdl-panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
      >
        <header className="mdl-head">
          <div className="min-w-0 flex-1">
            <h2 id={titleId} className="text-[19px] leading-snug">
              {title}
            </h2>
            {subtitle ? <p className="mut mt-1 text-[13px]">{subtitle}</p> : null}
          </div>
          <button type="button" className="mdl-x" onClick={onClose} aria-label="닫기">
            <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
              <path
                d="M3 3 L13 13 M13 3 L3 13"
                stroke="currentColor"
                strokeWidth="1.8"
                strokeLinecap="round"
              />
            </svg>
          </button>
        </header>

        {toolbar ? <div className="mdl-tools">{toolbar}</div> : null}

        <div className="mdl-body">{children}</div>

        {footer ? <div className="mdl-foot">{footer}</div> : null}
      </div>
    </div>,
    document.body,
  );
}
