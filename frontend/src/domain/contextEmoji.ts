/**
 * Context 이모지 — 초안 6c 관심도 평가 타일의 아이콘.
 *
 * 아이콘 세트일 뿐 Context 정본이 아니다. 이름·설명·지원 여부·순서는 전부
 * `GET /contexts`에서 온다. 여기 없는 context_id가 와도 화면은 정상 동작한다.
 */
const EMOJI: Record<string, string> = {
  game: "🎮",
  media: "🎬",
  school_life: "🎒",
  business: "💡",
  making: "🛠️",
  volunteer: "🤝",
  sports: "⚽",
  science: "🔬",
  writing: "📖",
  art_design: "🎨",
  travel: "🧭",
  cooking: "🍳",
  fashion_beauty: "👗",
  history_humanities: "🏛️",
  law_politics: "⚖️",
};

/** 모르는 Context는 중립 아이콘으로 떨어뜨린다 — 화면이 비지 않게. */
export function contextEmoji(contextId: string): string {
  return EMOJI[contextId] ?? "✨";
}
