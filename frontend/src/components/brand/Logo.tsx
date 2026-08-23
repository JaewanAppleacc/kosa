/**
 * TRAIL 로고 — 등산로처럼 방향을 꺾으며 올라가는 스위치백 Path.
 *
 * 초안 6a "라인의 세 가지 쓰임"을 이 Path 하나로 소화한다.
 *   mode="draw" 로고   — 한 번 그려지고 멈춘 뒤 마커 팝인 + 미세 breathing
 *   mode="loop" 로딩   — 같은 선이 계속 지나감 (회전 스피너를 따로 두지 않는다)
 *   mode="static"      — 완성된 상태로 고정 (상단 바 등)
 *
 * 색은 시스템 포인트색(--accent)을 따른다. 캐릭터나 얼굴은 쓰지 않는다.
 * prefers-reduced-motion에서는 전부 끄고 완성된 상태로 즉시 보여준다.
 */
import { useId } from "react";

const PATH = "M 12 84 L 40 84 L 40 60 L 16 60 L 16 36 L 44 36 L 44 16 L 76 16";
/** stroke-dasharray/offset에 쓸 대략적인 Path 길이. 실제보다 넉넉하면 되므로 상수로 둔다. */
const PATH_LENGTH = 240;

export type LogoMode = "draw" | "loop" | "static";

export function Logo({
  size = 88,
  mode,
  animate = true,
  className = "",
}: {
  size?: number;
  mode?: LogoMode;
  /** 뒤늦게 붙은 편의 인자 — animate={false}는 mode="static"과 같다. */
  animate?: boolean;
  className?: string;
}) {
  const gradientId = useId();
  const resolved: LogoMode = mode ?? (animate ? "draw" : "static");
  const isLoop = resolved === "loop";
  const isDraw = resolved === "draw";

  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 96 96"
      fill="none"
      role="img"
      aria-label={isLoop ? "불러오는 중" : "TRAIL 로고"}
      className={className}
    >
      <defs>
        <linearGradient id={gradientId} x1="0" y1="96" x2="96" y2="0" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="var(--accent)" />
          <stop offset="100%" stopColor="var(--color-accent-400)" />
        </linearGradient>
      </defs>

      <path
        d={PATH}
        stroke={`url(#${gradientId})`}
        strokeWidth="9"
        strokeLinecap="round"
        strokeLinejoin="round"
        className={isDraw ? "trail-logo-path" : isLoop ? "trail-line-loop" : undefined}
        style={
          isDraw || isLoop
            ? { strokeDasharray: PATH_LENGTH, strokeDashoffset: PATH_LENGTH }
            : undefined
        }
      />

      {/* 마커는 목적지 표시다 — 축하 연출이 아니라서 로딩 중에는 띄우지 않는다. */}
      {isLoop ? null : (
        <circle
          cx="76"
          cy="16"
          r="8"
          fill="var(--accent)"
          className={isDraw ? "trail-logo-marker" : undefined}
          style={isDraw ? { transformOrigin: "76px 16px", transform: "scale(0)" } : undefined}
        />
      )}
    </svg>
  );
}
