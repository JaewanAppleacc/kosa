/**
 * Career Profile 결과 카드 — 초안 6f.
 *
 * title은 "~보여요" 형태의 관찰 문장이지 유형 라벨이 아니다 — 유형 뱃지처럼 감싸지 않고
 * 문장 그대로 보여주고, 확정된 결론이 아니라는 안내를 항상 함께 둔다.
 */
import { useState } from "react";
import { fetchProfile } from "@/api/endpoints";
import { ErrorView } from "@/components/ErrorView";
import { Button, Card, Spinner } from "@/components/ui";
import { useAsync } from "@/hooks/useAsync";
import { useAppState } from "@/session/AppState";

export function ProfileScreen() {
  const { state } = useAppState();
  const [showEvidence, setShowEvidence] = useState(false);

  const profile = useAsync(
    (signal) => {
      if (!state.sessionId) return Promise.reject(new Error("세션이 없습니다."));
      return fetchProfile(state.sessionId, signal);
    },
    [state.sessionId],
  );

  if (profile.status === "loading" || profile.status === "idle") {
    return (
      <div className="grid place-items-center py-20">
        <Spinner label="결과를 정리하는 중" />
      </div>
    );
  }
  if (profile.status === "error") return <ErrorView error={profile.error} onRetry={profile.reload} />;

  const data = profile.data;
  const dimensions = Object.entries(data.detailed_evidence_by_dimension);

  return (
    <div className="flex flex-col gap-5">
      <Card>
        <h2 className="mb-5 text-[clamp(22px,4.5vw,30px)] leading-[1.35]">{data.title}</h2>

        {data.hashtags.length > 0 ? (
          <ul className="mb-6 flex flex-wrap gap-2">
            {data.hashtags.map((tag) => (
              <li key={tag}>
                <span className="htag">{tag}</span>
              </li>
            ))}
          </ul>
        ) : null}

        <ul className="flex flex-col gap-2.5">
          {data.highlights.map((highlight, index) => (
            <li key={`${index}-${highlight.text.slice(0, 8)}`} className="hlrow">
              <span aria-hidden="true" className="flex-none" style={{ color: "var(--accent)" }}>
                ●
              </span>
              <span>{highlight.text}</span>
            </li>
          ))}
        </ul>
      </Card>

      {dimensions.length > 0 ? (
        <Card>
          <div className="flex flex-wrap items-center gap-3">
            <p className="gsec flex-1">더 자세히</p>
            <Button variant="secondary" size="sm" onClick={() => setShowEvidence((v) => !v)} aria-expanded={showEvidence}>
              {showEvidence ? "근거 접기" : "왜 이런 결과가 나왔나요?"}
            </Button>
          </div>

          {showEvidence ? (
            <div className="mt-5 flex flex-col gap-5">
              {dimensions.map(([dimension, items]) => (
                <div key={dimension}>
                  <h3 className="mb-2 text-[16px]">{dimension}</h3>
                  <ul className="flex flex-col gap-1.5">
                    {items.map((item, index) => (
                      <li key={`${item.context_id}-${index}`} className="mut text-[14px] leading-relaxed">
                        · {item.description}
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          ) : null}
        </Card>
      ) : null}

      {/* API가 내려주는 안내 문구. 박스로 감싸지 않고 본문 아래 회색 글씨로만 둔다. */}
      <p className="mut px-1 text-[12.5px] leading-relaxed">
        {data.disclaimer} 성격을 유형으로 나누는 검사가 아니에요.
      </p>
    </div>
  );
}
