/**
 * TRAIL 마크 — 이야기를 이어 만든 경로.
 *
 * 왼쪽 아래에서 오른쪽 위로 꺾여 올라가는 길에 점 네 개를 얹었다. 출발점(속 빈 원),
 * 지나온 이야기(흰 점 둘), 그리고 "지금 여기"(가운데가 뚫린 도넛).
 *
 * 곡선(S자) 안을 몇 번 시도했는데 알파벳 S로 읽혀서 접었다. 직선 + 둥근 이음매가
 * 32px 상단 바에서도 뭉개지지 않는다.
 *
 * 초안 6a "라인의 세 가지 쓰임"을 이 Path 하나로 소화한다.
 *   mode="draw" 로고   — 한 번 그려지고 멈춘 뒤 점들이 차례로 들어온다
 *   mode="loop" 로딩   — 길이 그려지고 그 위를 점 하나가 걸어간다
 *                        (회전 스피너를 따로 두지 않는다)
 *   mode="static"      — 완성된 상태로 고정 (상단 바 등)
 *
 * 색은 시스템 포인트색(--accent)을 따른다. 캐릭터나 얼굴은 쓰지 않는다.
 * prefers-reduced-motion에서는 전부 끄고 완성된 상태로 즉시 보여준다.
 */
import { useId, type CSSProperties } from "react";

const START = { x: 16, y: 78 };
const WAYPOINTS = [
  { x: 42, y: 66 },
  { x: 34, y: 42 },
];
const END = { x: 76, y: 22 };
const PATH = `M ${START.x} ${START.y} L ${WAYPOINTS.map((p) => `${p.x} ${p.y}`).join(" L ")} L ${END.x} ${END.y}`;
/**
 * pathLength로 길이를 100에 고정한다 — 실제 경로 길이를 상수로 어림잡지 않아도
 * dasharray/offset이 정확히 맞아떨어진다(Path를 손보면 예전엔 상수도 같이 고쳐야 했다).
 */
const NORMALIZED_LENGTH = 100;

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
  // 로딩 중에는 선만 지나간다 — 지나온 자리와 도착점을 같이 두면 "다 왔다"로 읽힌다.
  const showNodes = !isLoop;

  return (
    <svg
      width={size}
      height={size}
      viewBox="4 6 86 86"
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
        pathLength={NORMALIZED_LENGTH}
        stroke={`url(#${gradientId})`}
        strokeWidth="7.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        className={isDraw ? "trail-logo-path" : isLoop ? "trail-walk-line" : undefined}
        style={
          isDraw || isLoop
            ? { strokeDasharray: NORMALIZED_LENGTH, strokeDashoffset: NORMALIZED_LENGTH }
            : undefined
        }
      />

      {/*
        로딩 — 길을 걸어가는 것처럼 보이게 한다. 바깥 <g>가 경로를 따라 이동하고(offset-path),
        안쪽 원이 위아래로 까딱거려서 미끄러지지 않고 걷는 느낌을 낸다.
        offset-path를 모르는 브라우저에서는 원이 출발점에 가만히 있는다 — 선은 그대로 그려지므로
        로딩 표시 자체는 유지된다.
      */}
      {isLoop ? (
        <g className="trail-walker" style={{ offsetPath: `path("${PATH}")` } as CSSProperties}>
          <circle className="trail-walker-foot" r="6" fill="var(--accent)" />
        </g>
      ) : null}

      {showNodes ? (
        <>
          {/* 출발점 — 어디서 시작했는지. 선이 다 그려진 뒤에 나타난다. */}
          <circle
            cx={START.x}
            cy={START.y}
            r="4.2"
            fill="#fff"
            stroke="var(--accent)"
            strokeWidth="3"
            className={isDraw ? "trail-logo-start" : undefined}
            style={isDraw ? { transformOrigin: `${START.x}px ${START.y}px` } : undefined}
          />

          {/* 지나온 이야기. 아주 작을 땐 선을 갉아먹어서 생략한다. */}
          {size >= 40
            ? WAYPOINTS.map((point, index) => (
                <circle
                  key={`${point.x}-${point.y}`}
                  cx={point.x}
                  cy={point.y}
                  r="3.2"
                  fill="#fff"
                  className={isDraw ? "trail-logo-start" : undefined}
                  style={
                    isDraw
                      ? {
                          transformOrigin: `${point.x}px ${point.y}px`,
                          animationDelay: `${1.15 + index * 0.1}s`,
                        }
                      : undefined
                  }
                />
              ))
            : null}

          {/* 도착 마커는 "지금 여기" 표시다 — 축하 연출이 아니라 로딩 중에는 띄우지 않는다. */}
          <circle
            cx={END.x}
            cy={END.y}
            r="9"
            fill="var(--accent)"
            className={isDraw ? "trail-logo-marker" : undefined}
            style={isDraw ? { transformOrigin: `${END.x}px ${END.y}px`, transform: "scale(0)" } : undefined}
          />
          <circle
            cx={END.x}
            cy={END.y}
            r="3.4"
            fill="#fff"
            className={isDraw ? "trail-logo-marker" : undefined}
            style={isDraw ? { transformOrigin: `${END.x}px ${END.y}px`, transform: "scale(0)" } : undefined}
          />
        </>
      ) : null}
    </svg>
  );
}

/**
 * 워드마크 — 마크와 글자를 같은 규칙으로 묶는다.
 *
 * 글자 뒤의 점은 마크 끝의 도착 마커와 같은 뜻이다(같은 색·같은 모양). 서비스 이름만
 * 크게 두면 무슨 서비스인지 알 수 없어서, 큰 크기에서는 한 줄 설명을 함께 둔다.
 */
export function Wordmark({
  size = "sm",
  showTagline = false,
}: {
  size?: "sm" | "lg";
  showTagline?: boolean;
}) {
  const large = size === "lg";
  return (
    <span className="wmark">
      <span className={large ? "wmark-name wmark-lg" : "wmark-name"}>
        TRAIL
        <i aria-hidden="true" />
      </span>
      {showTagline ? <span className="wmark-tag">좋아하는 이야기로 그리는 진로·학업 지도</span> : null}
    </span>
  );
}
