/**
 * Career Profile 결과 카드 — 초안 6f.
 *
 * title은 "~보여요" 형태의 관찰 문장이지 유형 라벨이 아니다 — 유형 뱃지처럼 감싸지 않고
 * 문장 그대로 보여주고, 확정된 결론이 아니라는 안내를 항상 함께 둔다.
 *
 * 화면에 숫자로 등장하는 건 "관찰된 답변 개수"뿐이다(TraitMap). 내부 점수·유사도는
 * 계약에 없고, 막대나 퍼센트 같은 모양으로 되살리지도 않는다.
 */
import { useCallback, useState } from "react";
import { fetchContextCatalog, fetchProfile } from "@/api/endpoints";
import { AnalyzingView } from "@/components/AnalyzingView";
import { ErrorView } from "@/components/ErrorView";
import { Button, Card } from "@/components/ui";
import { contextEmoji } from "@/domain/contextEmoji";
import { useAsync } from "@/hooks/useAsync";
import { useAppState } from "@/session/AppState";
import { TraitMap } from "./TraitMap";

export function ProfileScreen() {
  const { state, dispatch } = useAppState();
  const [showEvidence, setShowEvidence] = useState(false);

  const profile = useAsync(
    (signal) => {
      if (!state.sessionId) return Promise.reject(new Error("세션이 없습니다."));
      return fetchProfile(state.sessionId, signal);
    },
    [state.sessionId],
  );

  // 이름표만 쓰는 용도라 실패해도 결과 표시를 막지 않는다 — 그때는 id를 그대로 쓴다.
  const catalog = useAsync((signal) => fetchContextCatalog(signal), []);
  const labelOf = useCallback(
    (contextId: string) => {
      if (catalog.status !== "success") return contextId;
      return catalog.data.contexts.find((c) => c.context_id === contextId)?.label ?? contextId;
    },
    [catalog],
  );

  if (profile.status === "loading" || profile.status === "idle") {
    return (
      <AnalyzingView
        description="고른 답들을 한자리에 놓고, 반복해서 나타난 모습을 찾는 중이에요."
        steps={[
          "고른 답을 순서대로 모으는 중",
          "여러 분야에 걸쳐 반복된 모습을 찾는 중",
          "읽을 수 있는 문장으로 정리하는 중",
        ]}
      />
    );
  }
  if (profile.status === "error") return <ErrorView error={profile.error} onRetry={profile.reload} />;

  const data = profile.data;
  const dimensions = Object.entries(data.detailed_evidence_by_dimension);
  const hasEvidence = dimensions.length > 0;

  return (
    <div className="flex flex-col gap-5">
      <Card className="phero">
        <HeroDecor />

        <div className="relative">
          <p className="gsec">지금까지의 답변 요약</p>
          <h2 className="mb-4 max-w-[24ch] text-[clamp(22px,4.5vw,30px)] leading-[1.35]">
            {data.title}
          </h2>
          <p className="mut mb-6 text-[12.5px]">{formatCompletedAt(data.generated_at)}</p>

          {data.hashtags.length > 0 ? (
            <ul className="mb-7 flex flex-wrap gap-2">
              {data.hashtags.map((tag, index) => (
                <li key={tag}>
                  <span
                    className="htag reveal"
                    style={{ animationDelay: `${Math.min(index, 8) * 60}ms` }}
                  >
                    {tag}
                  </span>
                </li>
              ))}
            </ul>
          ) : null}

          <ul className="flex flex-col gap-2.5">
            {data.highlights.map((highlight, index) => (
              <li
                key={`${index}-${highlight.text.slice(0, 8)}`}
                className="hlrow reveal"
                style={{ animationDelay: `${Math.min(index, 8) * 55}ms` }}
              >
                <span aria-hidden="true" className="flex-none" style={{ color: "var(--accent)" }}>
                  ●
                </span>
                <span>{highlight.text}</span>
              </li>
            ))}
          </ul>
        </div>
      </Card>

      {hasEvidence ? (
        <Card>
          <p className="gsec">어디에서 나타났나요</p>
          <h3 className="mb-1.5 text-[18px]">고른 답이 어느 이야기에서 나왔는지</h3>
          <p className="sub mb-5">
            칸을 누르면 그때 어떤 답을 골랐는지 그대로 볼 수 있어요.
          </p>
          <TraitMap evidenceByDimension={data.detailed_evidence_by_dimension} labelOf={labelOf} />
        </Card>
      ) : null}

      {hasEvidence ? (
        <Card>
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex-1">
              <p className="gsec">더 자세히</p>
              <h3 className="text-[18px]">고른 답을 영역별로 모아보기</h3>
            </div>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setShowEvidence((v) => !v)}
              aria-expanded={showEvidence}
            >
              {showEvidence ? "근거 접기" : "왜 이런 결과가 나왔나요?"}
            </Button>
          </div>

          {showEvidence ? (
            <div className="mt-5 flex flex-col gap-5">
              {dimensions.map(([dimension, items], index) => (
                <div
                  key={dimension}
                  className="reveal"
                  style={{ animationDelay: `${Math.min(index, 8) * 45}ms` }}
                >
                  <h4 className="mb-2 text-[16px]">{dimension}</h4>
                  <ul className="flex flex-col gap-1.5">
                    {items.map((item, itemIndex) => (
                      <li
                        key={`${item.context_id}-${itemIndex}`}
                        className="mut flex gap-2 text-[14px] leading-relaxed"
                      >
                        <span aria-hidden="true" className="flex-none">
                          {contextEmoji(item.context_id)}
                        </span>
                        <span>{item.description}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          ) : null}
        </Card>
      ) : null}

      <Card>
        <p className="gsec">다음으로</p>
        <p className="sub mb-4">
          이 경향과 이어지는 전공을 묶어서 정리해뒀어요. 마음에 드는 전공을 고르면 그 전공에
          맞는 과목까지 이어서 볼 수 있어요.
        </p>
        <Button size="sm" onClick={() => dispatch({ type: "result_tab_changed", tab: "majors" })}>
          이어지는 전공 보러가기
        </Button>
      </Card>

      {/* API가 내려주는 안내 문구. 박스로 감싸지 않고 본문 아래 회색 글씨로만 둔다. */}
      <p className="mut px-1 text-[12.5px] leading-relaxed">
        {data.disclaimer} 성격을 유형으로 나누는 검사가 아니에요.
      </p>
    </div>
  );
}

/**
 * 결과 카드 장식 — 로고와 같은 스위치백 선을 크게 눕혀 깔고 블롭 두 개를 더한다.
 * 초안 규칙대로 캐릭터나 얼굴은 쓰지 않는다(선의 굵기와 색만 바꿔 쓴다).
 */
function HeroDecor() {
  return (
    <svg className="phero-decor" viewBox="0 0 200 120" aria-hidden="true" focusable="false">
      <circle cx="150" cy="30" r="46" fill="var(--color-accent-100)" />
      <circle cx="182" cy="92" r="30" fill="var(--color-accent-2-100)" />
      {/* 마크와 같은 경로 모양을 눕혀 깐다(다른 그림을 새로 만들지 않는다). */}
      <path
        d="M 24 104 L 62 86 L 50 52 L 116 22"
        fill="none"
        stroke="var(--accent)"
        strokeWidth="7"
        strokeLinecap="round"
        strokeLinejoin="round"
        opacity="0.16"
      />
      <circle cx="116" cy="22" r="8" fill="var(--accent)" opacity="0.22" />
    </svg>
  );
}

/** 서버가 준 ISO 문자열을 그대로 읽어 보여준다 — 날짜를 만들어내지 않는다. */
function formatCompletedAt(isoString: string): string {
  const date = new Date(isoString);
  if (Number.isNaN(date.getTime())) return "";
  return `${date.getFullYear()}년 ${date.getMonth() + 1}월 ${date.getDate()}일 정리됨`;
}
