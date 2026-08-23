/**
 * "정리하는 중" 화면 — 결과를 만드는 동안 빈 화면 대신 무엇을 하고 있는지 보여준다.
 *
 * 진학사 전공적성검사의 분석 대기 화면과 같은 자리지만, 한 가지를 다르게 했다:
 * **"완료" 체크를 미리 찍지 않는다.** 단계 문구는 시간이 지나면 다음으로 넘어가되,
 * 마지막 단계는 실제 응답이 올 때까지 계속 진행 중으로 남는다. 응답이 도착하면 이
 * Component 자체가 사라지므로, 화면에 "끝났다"는 표시가 뜨는 순간과 실제로 끝난
 * 순간이 어긋나지 않는다.
 */
import { useEffect, useState } from "react";
import { Logo } from "@/components/brand/Logo";

const STEP_MS = 1500;

export function AnalyzingView({
  title = "답변을 정리하고 있어요",
  description,
  steps,
}: {
  title?: string;
  description?: string;
  steps: string[];
}) {
  const [reached, setReached] = useState(0);

  useEffect(() => {
    if (reached >= steps.length - 1) return;
    const timer = window.setTimeout(() => setReached((n) => n + 1), STEP_MS);
    return () => window.clearTimeout(timer);
  }, [reached, steps.length]);

  return (
    <div className="grid place-items-center py-16" role="status" aria-live="polite">
      <Logo size={64} mode="loop" />

      <h2 className="mt-6 text-center text-[21px] leading-snug">{title}</h2>
      {description ? <p className="sub mt-2 text-center">{description}</p> : null}

      <ul className="mt-7 flex w-full max-w-[420px] flex-col gap-2">
        {steps.map((step, index) => {
          const done = index < reached;
          const active = index === reached;
          return (
            <li
              key={step}
              className={`astep${done ? " done" : ""}${active ? " active" : ""}`}
              style={{ animationDelay: `${Math.min(index, 6) * 70}ms` }}
            >
              <span className="astep-dot" aria-hidden="true">
                {done ? (
                  <svg width="11" height="11" viewBox="0 0 12 12">
                    <path
                      d="M2.5 6.4 L4.9 8.8 L9.5 3.4"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="1.9"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                ) : null}
              </span>
              <span>{step}</span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
