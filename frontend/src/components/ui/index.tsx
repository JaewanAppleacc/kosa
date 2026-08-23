/**
 * UI 조각 — Claude Design 캔버스 초안(6a 브랜드 시트)의 규칙을 그대로 따른다.
 *
 * · 버튼은 항상 필 모양(기본 높이 52px)
 * · 카드 24px 라운드, 타일 20px, 선택지 18px
 * · 그림자는 아주 약하게 한 단계만
 * · 캐릭터·얼굴은 쓰지 않는다. 선의 굵기와 색만 바꿔 쓴다.
 */
import type { ButtonHTMLAttributes, ReactNode } from "react";
import { Logo, Wordmark } from "@/components/brand/Logo";

type PillVariant = "primary" | "secondary" | "outline" | "ghost";

const PILL_CLASS: Record<PillVariant, string> = {
  primary: "pill-pri",
  secondary: "pill-sec",
  outline: "pill-out",
  ghost: "pill-ghost",
};

export function Button({
  variant = "primary",
  size = "md",
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: PillVariant;
  size?: "sm" | "md" | "lg";
}) {
  const sizeStyle =
    size === "sm"
      ? { height: 40, fontSize: 14, padding: "0 20px" }
      : size === "lg"
        ? { height: 56, fontSize: 17, padding: "0 34px" }
        : undefined;
  return <button className={`pill ${PILL_CLASS[variant]} ${className}`} style={sizeStyle} {...props} />;
}

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`ct p-7 ${className}`}>{children}</div>;
}

/** 로딩 — 회전 스피너 대신 로고 선이 계속 지나간다(초안 "라인의 세 가지 쓰임"). */
export function Spinner({ label = "불러오는 중" }: { label?: string }) {
  return (
    <span className="inline-flex flex-col items-center gap-2.5" role="status">
      <Logo size={46} mode="loop" />
      <span className="text-[13px] mut">{label}</span>
    </span>
  );
}

export function StateBlock({
  tone = "neutral",
  title,
  description,
  action,
}: {
  tone?: "neutral" | "error";
  title: string;
  description?: ReactNode;
  action?: ReactNode;
}) {
  const isError = tone === "error";
  return (
    <div
      className="rounded-[20px] px-6 py-9 text-center"
      style={{
        background: isError ? "var(--color-accent-2-100)" : "#fff",
        boxShadow: `inset 0 0 0 1.5px ${isError ? "var(--color-accent-2-200)" : "var(--line)"}`,
      }}
      role={isError ? "alert" : undefined}
    >
      <p className="text-[17px] font-semibold" style={{ fontFamily: "var(--font-heading)" }}>
        {title}
      </p>
      {description ? <div className="mt-2 text-sm leading-relaxed mut">{description}</div> : null}
      {action ? <div className="mt-5 flex flex-wrap justify-center gap-2">{action}</div> : null}
    </div>
  );
}

/** 정성 Label 표시용. 내부 점수를 배지로 바꿔 보여주는 용도가 아니다. */
export function Badge({
  children,
  tone = "accent",
}: {
  children: ReactNode;
  tone?: "accent" | "quiet" | "blush";
}) {
  const cls = tone === "quiet" ? "chip chip-quiet" : tone === "blush" ? "chip chip-blush" : "chip";
  return <span className={`${cls} text-[12.5px]`}>{children}</span>;
}

export function SectionTitle({ children, hint }: { children: ReactNode; hint?: ReactNode }) {
  return (
    <div className="mb-4">
      <h2 className="text-[22px] leading-[1.4]">{children}</h2>
      {hint ? <p className="sub mt-1.5">{hint}</p> : null}
    </div>
  );
}

/** Context 진행도 — 질문 수가 아니라 "몇 번째 영역인지"만 나타낸다. */
export function ProgressBar({ value, max }: { value: number; max: number }) {
  const ratio = max > 0 ? Math.min(1, Math.max(0, value / max)) : 0;
  return (
    <div className="pbar" role="progressbar" aria-valuenow={value} aria-valuemin={0} aria-valuemax={max}>
      <span style={{ width: `${ratio * 100}%` }} />
    </div>
  );
}

/** 1~5 관심도 미니 스케일. 숫자를 쓰지 않고 점으로만 보여준다. */
export function MiniScale({ score, max = 5 }: { score: number | undefined; max?: number }) {
  return (
    <span className="mini" aria-hidden="true">
      {Array.from({ length: max }, (_, index) => (
        <i key={index} className={score !== undefined && index < score ? "on" : undefined} />
      ))}
    </span>
  );
}

/** 검사 단계 화면의 공통 폭. */
export function ScreenShell({ children, wide = false }: { children: ReactNode; wide?: boolean }) {
  return (
    <div className={`mx-auto w-full ${wide ? "max-w-5xl" : "max-w-3xl"} px-5 py-8 sm:px-8`}>{children}</div>
  );
}

/** 상단 바 — 로고 + 자동 저장 안내. 초안 6c/6e/6f의 nav2. */
export function TopBar({ right }: { right?: ReactNode }) {
  return (
    <div className="nav2">
      <span className="flex items-center gap-2.5">
        <Logo size={32} animate={false} />
        <Wordmark />
      </span>
      <span className="ml-auto flex items-center gap-3.5">{right}</span>
    </div>
  );
}
