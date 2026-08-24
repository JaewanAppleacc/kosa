"use strict";

/* V2 Direct Probe 검수 UI 클라이언트 — 2026-08-23 Trait Ontology v2(2.4단계) §2/§12.
 *
 * 이 스크립트는 어떤 항목도 스스로 APPROVE/REVISE/HOLD로 정하지 않는다 — 사람이 화면에서
 * 고른 값을 그대로 서버에 보낼 뿐이다. innerHTML로 데이터(질문/선택지/코멘트 원문)를
 * 삽입하지 않는다 — 전부 textContent/DOM API로만 넣는다.
 */

const API_BASE = "/internal/review/v2";

const state = {
  questions: [],
  summary: null,
  questionRevision: null,
  optionRevision: null,
  reviewerSlot: "", // "" | "reviewer_1" | "reviewer_2"
  mode: "student", // "student" | "mapping"
  tab: "direct_probe", // "direct_probe" | "routing" | "seed_anchor" — 질문 유형 탭
  currentIndex: 0,
  filters: { status: "all", questionFlag: false, optionFlag: false, noSignal: false, lengthHistory: false, trait: "", context: "" },
  dirty: false, // 저장하지 않은 변경사항 존재 여부(현재 열린 편집 영역 기준)
  // 2.5단계 §10 — Context Routing 탭 전용 상태. v2 Direct Probe 상태와 완전히 분리한다.
  routingQuestions: [],
  routingQuestionRevision: null,
  routingOptionRevision: null,
  routingCurrentIndex: 0,
  // 2.5.2단계 §12 — Seed Anchor Variant 탭 전용 상태.
  seedAnchorQuestions: [],
  seedAnchorQuestionRevision: null,
  seedAnchorOptionRevision: null,
  seedAnchorCurrentIndex: 0,
  // 2.5.3단계 §11 — Backup Question 탭 전용 상태.
  backupQuestions: [],
  backupQuestionRevision: null,
  backupOptionRevision: null,
  backupCurrentIndex: 0,
  // 2.5.4단계 §7 — Anchor Backup 탭 전용 상태(기존 Backup 탭과 완전히 분리).
  anchorBackupQuestions: [],
  anchorBackupQuestionRevision: null,
  anchorBackupOptionRevision: null,
  anchorBackupCurrentIndex: 0,
  // 2026-08-24 Trait Ontology v2(2.9.1단계) §5 — ContextPack 공용 Adaptive Probe 탭
  // 전용 상태. Blueprint → Context → Anchor 3단 구조라 다른 탭의 "질문 하나 = Pager
  // 한 칸" 모델을 그대로 쓰지 않는다 — 사이드바에서 Blueprint를 고르면 그 Blueprint의
  // 12개 Context 행이 전부 펼쳐져 보인다.
  sharedProbes: [],
  sharedProbeCurrentBlueprintId: null,
  // 2026-08-24 배치별 Shared Probe 검수 화면 — 840개(14×12×5) Anchor 판단이 한
  // 화면에 섞이는 문제를 풀기 위해 배치(1/2/3/"all")·상태 필터를 추가한다. 기본값은
  // 지시서 §3/§6 그대로 1차 배치 + "미판정 Anchor 있음"이다.
  sharedProbeBatch: 1, // 1 | 2 | 3 | "all"
  sharedProbeStatusFilter: "anchor_undetermined",
  // 2026-08-24 신규 ContextPack(business/science/sports 등 12개) 검수 탭 전용 상태.
  // Blueprint→Context→Anchor 3단인 shared_probes와 달리 이 탭은 "배치 → Context →
  // 질문(11개)" 3단이라 currentIndex 하나로는 부족해 batch/context/questionIndex를
  // 따로 둔다. reviewerSlot(위)을 그대로 공유한다 — "검토자 1"을 선택해야만 저장
  // 가능한 전역 게이트를 이 탭에도 동일하게 적용한다(지시서 §7의 "이 프로젝트는
  // reviewer_1만 사용한다"는 이미 이 게이트로 강제되고 있다).
  contextPacks: [],
  contextPackDiscoveryErrors: {},
  contextPackOntologyErrors: {},
  contextPackBatch: 1,
  contextPackContextId: null,
  contextPackQuestionIndex: 0,
  contextPackStatusFilter: "all",
  // 2026-08-24 지시서(a/canonical-major-bridge-review-ui) — Canonical Major Group
  // Bridge(44행) 검수 탭 전용 상태. 44행이라 Pager 없이 필터링된 카드 목록을 한
  // 화면에 그린다. bridgeFilters는 전부 순수 클라이언트 필터다 — 바뀌어도 저장
  // 요청을 절대 보내지 않는다(§5 "필터 변경만으로 저장 요청을 보내지 않음").
  bridgeRows: [],
  bridgeSummary: null,
  bridgeFilters: { mapping: "all", reviewStatus: "all", boundary: false, major: "all" },
};

// 2.5단계 §10 — Routing 질문은 Trait Mapping이 없으므로 체크리스트도 다르다: "정답처럼
// 보이는 선택지가 없는가"(사회적 바람직성) 대신 "하위 Context가 서로 겹치지 않게
// 구분되는가", "특정 학생을 배제하지 않는가", "선택지 의미가 서로 겹치지 않는가",
// "Trait 채점으로 오인될 위험이 없는가"를 사람이 직접 판단한다.
const CHECKLIST_ROUTING_QUESTION = [
  "5개 선택지의 하위 Context(Anchor)가 서로 명확히 구분된다",
  "특정 플레이 방식·감상 취향·교우 관계를 가진 학생을 배제하지 않는다",
  "선택지 의미가 서로 겹치지 않는다(하나를 고르면 다른 것도 맞는 것처럼 읽히지 않는다)",
  "이 질문이나 선택지가 Trait를 채점하는 질문처럼 보이지 않는다",
];

const CHECKLIST_ROUTING_OPTION = [
  "이 선택지가 가리키는 하위 Context 이름이 실제 문장과 어울린다",
  "다른 선택지와 문구가 겹치지 않는다",
  "이 선택지를 고른다고 해서 특정 성향이 더 낫다는 인상을 주지 않는다",
];

// 2.5.2단계 §12 — Seed Anchor Variant는 Trait Mapping을 실제로 갖고 있으므로(중립
// Seed와 같은 role_id·primary_trait_delta), V2 Direct Probe 체크리스트와 비슷하지만
// "중립 문구와 비교했을 때 의미가 바뀌지 않았는가"가 이 유형에서만 중요한 항목이다.
const CHECKLIST_SEED_ANCHOR_QUESTION = [
  "Anchor 상황으로 바뀌어도 5개 Trait가 관찰될 수 있는 넓은 상황이다",
  "중립(Anchor 없음) 질문과 비교했을 때 의미가 달라지지 않았다",
  "고등학생이 이해하기 자연스럽다",
];

const CHECKLIST_SEED_ANCHOR_OPTION = [
  "문장이 연결된 Trait 행동을 직접 나타낸다",
  "단순 관심·감상만으로 능력이나 성향을 추론하지 않는다",
  "중립 선택지와 비교했을 때 Mapping 의미가 변질되지 않았다",
  "Mapping Rationale Draft가 이 문장과 실제로 맞아떨어진다",
];

// 2.5.3단계 §11 — Backup Question은 특정 Anchor 없이도(Anchor 답변 전 세션 포함) 나갈
// 수 있어야 하므로, "특정 장르·Anchor에 종속되지 않는가"가 이 유형에서만 중요하다.
const CHECKLIST_BACKUP_QUESTION = [
  "특정 Anchor를 선택하지 않은 학생도 자연스럽게 답할 수 있다",
  "현재 재정의된 Context와 일치한다",
  "질문 상황과 5개 선택지가 자연스럽게 이어진다",
];

const CHECKLIST_BACKUP_OPTION = [
  "문장이 연결된 Trait 행동을 직접 나타낸다",
  "단순 감상·관찰만으로 능력이나 표현을 추론하지 않는다",
  "다른 선택지를 전부 포괄하는 표현이 아니다",
  "사회적으로 바람직한 정답처럼 보이지 않는다",
];

// 2026-08-24 신규 ContextPack 검수 탭 전용 체크리스트(지시서 §9) — 게임/미디어/학교생활
// 전용 문구를 쓰는 기존 CHECKLIST_ROUTING_*/CHECKLIST_SEED_ANCHOR_*와 달리, 12개
// 신규 Context(업종·소재가 서로 다름) 어디에나 적용 가능한 일반 문구를 쓴다. 다른
// 체크리스트와 마찬가지로 검토 보조 수단일 뿐 — 어떤 값도 서버로 전송하지 않는다.
const CHECKLIST_CONTEXTPACK_ROUTING = [
  "5개 Anchor가 명확히 구분된다",
  "특정 경험을 부당하게 전제하지 않는다",
  "선택지 의미가 과도하게 겹치지 않는다",
  "Trait를 채점하는 질문처럼 보이지 않는다",
];

const CHECKLIST_CONTEXTPACK_SEED_BACKUP = [
  "질문이 해당 Anchor 상황에 맞는다",
  "선택지 5개가 질문에 자연스럽게 답한다",
  "선택지와 Trait Mapping이 직접적으로 연결된다",
  "NO_SIGNAL이 억지 Trait로 매핑되지 않았다",
  "모범답안처럼 보이는 선택지가 없다",
  "다른 선택지를 포괄하는 선택지가 없다",
  "학생에게 자연스러운 문장이다",
];

const CONTEXTPACK_KIND_LABEL = {
  routing: "Routing", seed: "Seed", anchor_backup: "Anchor Backup", direct_probe: "Native Direct Probe",
};
const CONTEXTPACK_KIND_ORDER = { routing: 0, seed: 1, anchor_backup: 2, direct_probe: 3 };
const CONTEXTPACK_BATCH_LABEL = { 1: "1차 배치", 2: "2차 배치", 3: "3차 배치" };

const CHECKLIST_QUESTION = [
  "고등학생이 이해하기 자연스럽다",
  "특정 선택지가 정답처럼 보이지 않는다",
  "사회적으로 바람직한 답을 유도하지 않는다",
  "선택지 길이와 구체성이 균형적이다",
  "선택지 간 의미가 충분히 구분된다",
  "목표 Trait를 관찰하기에 적합한 상황이다",
];

const CHECKLIST_OPTION = [
  "PRIMARY Mapping이 타당하다",
  "RELATED Mapping이 과도하지 않다",
  "NO_SIGNAL 판정이 적절하다",
  "이 선택지만 지나치게 긍정적으로 보이지 않는다",
  "문장 의미와 Mapping 근거가 일치한다",
];

function el(tag, props, children) {
  const node = document.createElement(tag);
  if (props) {
    for (const [key, value] of Object.entries(props)) {
      if (key === "class") node.className = value;
      else if (key === "text") node.textContent = value;
      else if (key.startsWith("on") && typeof value === "function") node.addEventListener(key.slice(2), value);
      else node.setAttribute(key, value);
    }
  }
  if (children) {
    for (const child of Array.isArray(children) ? children : [children]) {
      if (child == null) continue;
      node.appendChild(typeof child === "string" ? document.createTextNode(child) : child);
    }
  }
  return node;
}

function statusPill(status) {
  return el("span", { class: `status-pill ${status}`, text: status });
}

async function apiGet(path) {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`GET ${path} 실패 (${res.status})`);
  return res.json();
}

async function apiPatch(path, body) {
  const res = await fetch(path, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = new Error(data && data.detail && data.detail.error ? data.detail.error : `저장 실패 (${res.status})`);
    err.status = res.status;
    throw err;
  }
  return data;
}

function setSaveIndicator(text, cls) {
  const node = document.getElementById("save-indicator");
  node.textContent = text;
  node.className = `save-indicator ${cls || ""}`;
}

async function loadAll() {
  setSaveIndicator("불러오는 중…", "");
  const [questionsResp, summary] = await Promise.all([
    apiGet(`${API_BASE}/questions`),
    apiGet(`${API_BASE}/summary`),
  ]);
  state.questions = questionsResp.questions;
  state.questionRevision = questionsResp.question_review_revision;
  state.optionRevision = questionsResp.option_review_revision;
  state.summary = summary;
  populateFilterOptions();
  renderSummary();
  renderSidebarList();
  renderCurrentQuestion();
  setSaveIndicator("불러옴", "saved");
}

async function reloadAfterConflict() {
  if (state.dirty) {
    const proceed = confirm("저장하지 않은 변경사항이 있습니다. 새로고침하면 사라집니다. 계속할까요?");
    if (!proceed) return;
  }
  state.dirty = false;
  await loadAll();
}

function populateFilterOptions() {
  const traitSelect = document.getElementById("filter-trait");
  const contextSelect = document.getElementById("filter-context");
  const traits = new Map();
  const contexts = new Map();
  for (const q of state.questions) {
    traits.set(q.trait_id, q.trait_label);
    contexts.set(q.context_id, q.context_label);
  }
  traitSelect.replaceChildren(el("option", { value: "" }, "전체"));
  for (const [id, label] of traits) {
    traitSelect.appendChild(el("option", { value: id }, `${label} (${id})`));
  }
  contextSelect.replaceChildren(el("option", { value: "" }, "전체"));
  for (const [id, label] of contexts) {
    contextSelect.appendChild(el("option", { value: id }, label));
  }
}

function renderSummary() {
  const s = state.summary;
  const box = document.getElementById("summary-box");
  box.replaceChildren(
    el("div", { class: "row" }, [el("span", {}, "질문 검토"), el("span", { class: "n" }, `${s.question_reviewed_final} / ${s.question_total}`)]),
    el("div", { class: "row" }, [el("span", {}, "선택지 검토"), el("span", { class: "n" }, `${s.option_reviewed_final} / ${s.option_total}`)]),
    el("div", { class: "row" }, [el("span", {}, "승인 완료 질문 수"), el("span", { class: "n" }, `${s.approved_eligible_blueprint_ids.length}`)]),
    el("div", { class: "row" }, [el("strong", {}, "질문 슬롯 분포")]),
    ...["APPROVE", "REVISE", "HOLD", "TBD"].map((k) =>
      el("div", { class: "row" }, [el("span", {}, k), el("span", { class: "n" }, String(s.question_status_counts[k] || 0))])
    ),
    el("div", { class: "row" }, [el("strong", {}, "선택지 슬롯 분포")]),
    ...["APPROVE", "REVISE", "HOLD", "TBD"].map((k) =>
      el("div", { class: "row" }, [el("span", {}, k), el("span", { class: "n" }, String(s.option_status_counts[k] || 0))])
    ),
  );
}

function questionMatchesFilters(q) {
  const f = state.filters;
  if (f.status !== "all") {
    const matchesQuestion = q.review.reviewer_1_status === f.status || q.review.reviewer_2_status === f.status;
    const matchesOption = q.options.some((o) => o.review.reviewer_1_status === f.status || o.review.reviewer_2_status === f.status);
    if (!matchesQuestion && !matchesOption) return false;
  }
  if (f.questionFlag && q.question_quality_flags.length === 0) return false;
  if (f.optionFlag && !q.options.some((o) => o.quality_flags.length > 0 || o.length_outlier)) return false;
  if (f.noSignal && !q.has_no_signal_option) return false;
  if (f.lengthHistory && !q.has_length_review_history) return false;
  if (f.trait && q.trait_id !== f.trait) return false;
  if (f.context && q.context_id !== f.context) return false;
  return true;
}

function filteredQuestions() {
  return state.questions.filter(questionMatchesFilters);
}

function renderSidebarList() {
  const list = document.getElementById("question-nav-list");
  list.replaceChildren();
  const visible = filteredQuestions();
  visible.forEach((q) => {
    const globalIndex = state.questions.indexOf(q);
    const item = el(
      "li",
      { class: globalIndex === state.currentIndex ? "current" : "", onclick: () => goToIndex(globalIndex) },
      [el("span", { text: `${q.trait_label} · ${q.context_label}` }), statusPill(q.review.final_status)],
    );
    list.appendChild(item);
  });
}

function confirmDiscardIfDirty() {
  if (!state.dirty) return true;
  const proceed = confirm("저장하지 않은 변경사항이 있습니다. 이동하면 사라집니다. 계속할까요?");
  if (proceed) state.dirty = false;
  return proceed;
}

function goToIndex(index) {
  if (!confirmDiscardIfDirty()) return;
  state.currentIndex = index;
  renderSidebarList();
  renderCurrentQuestion();
}

function stepQuestion(delta) {
  const visible = filteredQuestions();
  if (visible.length === 0) return;
  const currentQ = state.questions[state.currentIndex];
  let pos = visible.indexOf(currentQ);
  if (pos === -1) pos = 0;
  const nextPos = Math.min(Math.max(pos + delta, 0), visible.length - 1);
  goToIndex(state.questions.indexOf(visible[nextPos]));
}

function renderReviewerSlotBlock({ scope, blueprintId, roleId, review, onSaved, kind }) {
  const isSlot1Editable = state.reviewerSlot === "reviewer_1";
  const isSlot2Editable = state.reviewerSlot === "reviewer_2";

  const block1 = renderSingleSlotBlock({
    slot: "reviewer_1", label: "검토자 1", editable: isSlot1Editable,
    status: review.reviewer_1_status, comment: review.reviewer_1_comment,
    scope, blueprintId, roleId, onSaved, kind,
  });
  const block2 = renderSingleSlotBlock({
    slot: "reviewer_2", label: "검토자 2", editable: isSlot2Editable,
    status: review.reviewer_2_status, comment: review.reviewer_2_comment,
    scope, blueprintId, roleId, onSaved, kind,
  });

  const finalBadge = el("span", { class: `final-status-badge status-pill ${review.final_status}`, text: review.final_status });

  return el("div", { class: "review-panel" }, [
    el("div", {}, [el("strong", {}, "검토 상태 "), finalBadge]),
    el("div", { class: "slot-columns" }, [block1, block2]),
  ]);
}

function renderSingleSlotBlock({ slot, label, editable, status, comment, scope, blueprintId, roleId, onSaved, kind }) {
  const isRouting = kind === "routing";
  const isSeedAnchor = kind === "seed_anchor";
  const isAnchorBackup = kind === "anchor_backup";
  const isBackup = kind === "backup" || isAnchorBackup;
  const checklistItems = isRouting
    ? (scope === "question" ? CHECKLIST_ROUTING_QUESTION : CHECKLIST_ROUTING_OPTION)
    : isSeedAnchor
    ? (scope === "question" ? CHECKLIST_SEED_ANCHOR_QUESTION : CHECKLIST_SEED_ANCHOR_OPTION)
    : isBackup
    ? (scope === "question" ? CHECKLIST_BACKUP_QUESTION : CHECKLIST_BACKUP_OPTION)
    : (scope === "question" ? CHECKLIST_QUESTION : CHECKLIST_OPTION);

  if (!editable) {
    return el("div", { class: "reviewer-slot-block readonly" }, [
      el("h4", {}, [el("span", { text: label }), statusPill(status)]),
      el("p", { class: "inline-msg", text: comment || "(의견 없음)" }),
    ]);
  }

  const statusValue = { current: status };
  const radioGroup = el("div", { class: "status-radio-group" });
  ["TBD", "APPROVE", "REVISE", "HOLD"].forEach((value) => {
    const input = el("input", {
      type: "radio", name: `${scope}-${blueprintId}-${roleId || ""}-status`, value,
      onchange: () => { statusValue.current = value; markDirty(); },
    });
    if (status === value) input.setAttribute("checked", "checked");
    radioGroup.appendChild(el("label", {}, [input, document.createTextNode(value)]));
  });

  const commentBox = el("textarea", {
    class: "comment-box", placeholder: "검토 의견을 입력하세요",
    oninput: markDirty,
  });
  commentBox.value = comment || "";

  const checklist = el(
    "div", { class: "checklist" },
    checklistItems.map((text, i) =>
      el("label", {}, [el("input", { type: "checkbox", "data-checklist-index": String(i) }), document.createTextNode(text)])
    ),
  );

  const msg = el("span", { class: "inline-msg" });
  const saveBtn = el("button", { class: "save-btn", type: "button" }, "저장");
  saveBtn.addEventListener("click", async () => {
    saveBtn.disabled = true;
    msg.textContent = "";
    msg.className = "inline-msg";
    try {
      const routePrefix = isRouting ? "routing-questions"
        : isSeedAnchor ? "seed-anchor-questions"
        : isAnchorBackup ? "anchor-backup-questions"
        : isBackup ? "backup-questions"
        : "questions";
      const revisionKey = isRouting
        ? (scope === "question" ? "routingQuestionRevision" : "routingOptionRevision")
        : isSeedAnchor
        ? (scope === "question" ? "seedAnchorQuestionRevision" : "seedAnchorOptionRevision")
        : isAnchorBackup
        ? (scope === "question" ? "anchorBackupQuestionRevision" : "anchorBackupOptionRevision")
        : isBackup
        ? (scope === "question" ? "backupQuestionRevision" : "backupOptionRevision")
        : (scope === "question" ? "questionRevision" : "optionRevision");
      // Seed Anchor는 blueprintId 자리에 이미 "{context_id}/{anchor_id}"(각 segment는
      // 호출부에서 미리 encodeURIComponent된) 형태로 들어온다 — 여기서 다시 감싸면
      // 슬래시가 %2F로 이중 인코딩돼 경로가 깨진다.
      const blueprintPathSegment = isSeedAnchor ? blueprintId : encodeURIComponent(blueprintId);
      const path = scope === "question"
        ? `${API_BASE}/${routePrefix}/${blueprintPathSegment}`
        : `${API_BASE}/${routePrefix}/${blueprintPathSegment}/options/${encodeURIComponent(roleId)}`;
      const result = await apiPatch(path, {
        reviewer: slot, status: statusValue.current, comment: commentBox.value,
        expected_revision: state[revisionKey],
      });
      state[revisionKey] = result.new_revision;
      msg.textContent = "저장됨";
      msg.className = "inline-msg ok";
      state.dirty = false;
      if (isRouting) await refreshRoutingAfterSave();
      else if (isSeedAnchor) await refreshSeedAnchorAfterSave();
      else if (isAnchorBackup) await refreshAnchorBackupAfterSave();
      else if (isBackup) await refreshBackupAfterSave();
      else await refreshAfterSave();
      if (onSaved) onSaved();
    } catch (err) {
      if (err.status === 409) {
        msg.textContent = "충돌: 다른 곳에서 먼저 저장됨 — 새로고침이 필요합니다";
        msg.className = "inline-msg err";
        if (isRouting) await reloadRoutingAfterConflict();
        else if (isSeedAnchor) await reloadSeedAnchorAfterConflict();
        else if (isAnchorBackup) await reloadAnchorBackupAfterConflict();
        else if (isBackup) await reloadBackupAfterConflict();
        else await reloadAfterConflict();
      } else {
        msg.textContent = err.message || "저장 실패";
        msg.className = "inline-msg err";
      }
    } finally {
      saveBtn.disabled = false;
    }
  });

  return el("div", { class: "reviewer-slot-block editable" }, [
    el("h4", {}, [el("span", { text: `${label} (편집 중)` }), statusPill(status)]),
    radioGroup,
    commentBox,
    checklist,
    el("div", { class: "save-row" }, [saveBtn, msg]),
  ]);
}

async function refreshAfterSave() {
  // 저장 성공 후 요약·목록 상태를 최신화한다(전체 재로딩보다 가볍게, 서버를 다시 조회).
  const [questionsResp, summary] = await Promise.all([apiGet(`${API_BASE}/questions`), apiGet(`${API_BASE}/summary`)]);
  const currentBlueprintId = state.questions[state.currentIndex] ? state.questions[state.currentIndex].blueprint_id : null;
  state.questions = questionsResp.questions;
  state.questionRevision = questionsResp.question_review_revision;
  state.optionRevision = questionsResp.option_review_revision;
  state.summary = summary;
  if (currentBlueprintId) {
    const idx = state.questions.findIndex((q) => q.blueprint_id === currentBlueprintId);
    if (idx !== -1) state.currentIndex = idx;
  }
  renderSummary();
  renderSidebarList();
  renderCurrentQuestion();
}

function markDirty() {
  state.dirty = true;
}

function renderOptionCard(option, question) {
  const classes = ["option-card"];
  if (option.is_target) classes.push("is-target", "mode-mapping-target");
  if (option.mapping_type === "NO_SIGNAL") classes.push("is-nosignal", "mode-mapping-nosignal");

  const mappingDetails = el("div", { class: "mapping-only" }, [
    el("div", { class: "option-meta" }, [
      el("span", { text: `role_id: ${option.role_id}` }),
      el("span", { text: option.mapping_type === "NO_SIGNAL" ? "NO_SIGNAL" : "TRAIT_SIGNAL" }),
      option.is_target ? el("span", { text: "★ TARGET" }) : null,
    ]),
    option.mapping_type === "TRAIT_SIGNAL"
      ? el("div", { class: "option-meta" }, option.signals.map((s) =>
          el("span", { text: `${s.signal_role}: ${s.trait_id} (weight ${s.weight})` })
        ))
      : el("div", { class: "option-meta" }, [el("span", { text: `NO_SIGNAL 이유: ${option.no_signal_reason || "-"}` })]),
    option.quality_flags.length > 0
      ? el("div", {}, option.quality_flags.map((f) => el("span", { class: "flag-chip", text: f })))
      : null,
    option.length_review_before
      ? el("div", { class: "length-history" }, [
          el("div", {}, `수정 전: ${option.length_review_before}`),
          el("div", {}, `수정 후: ${option.length_review_after}`),
          el("div", {}, `이유: ${option.length_review_reason}`),
        ])
      : null,
  ]);

  const studentHint = el("div", { class: "student-hint option-meta" }, [
    el("span", { text: `글자 수: ${option.length}자` }),
  ]);

  const reviewPanel = renderReviewerSlotBlock({
    scope: "option", blueprintId: question.blueprint_id, roleId: option.role_id, review: option.review,
  });

  return el("li", { class: classes.join(" ") }, [
    el("div", { class: "option-text", text: `${option.display_order}. ${option.text}` }),
    studentHint,
    mappingDetails,
    reviewPanel,
  ]);
}

function renderQuestionCard(question) {
  const meta = el("div", { class: "meta" }, [
    el("span", { class: "student-hint", text: `Context: ${question.context_label}` }),
    el("span", { class: "mapping-only-inline", text: ` · blueprint_id: ${question.blueprint_id} · context_id: ${question.context_id} · frame_id: ${question.frame_id}` }),
  ]);

  const traitPanel = el("div", { class: "trait-panel mapping-only" }, [
    el("div", {}, [el("strong", { text: `목표 Trait: ${question.trait_label} (${question.trait_id})` })]),
    el("div", { class: "def", text: question.trait_definition }),
    question.distinction_notes ? el("div", { class: "def", text: `인접 Trait 구분: ${question.distinction_notes}` }) : null,
    question.neighboring_trait_ids.length
      ? el("div", { class: "neighbors", text: `인접 Trait: ${question.neighboring_trait_ids.join(", ")}` })
      : null,
    question.question_quality_flags.length
      ? el("div", {}, question.question_quality_flags.map((f) => el("span", { class: "flag-chip", text: f })))
      : null,
  ]);

  const optionList = el("ul", { class: "option-list" }, question.options.map((o) => renderOptionCard(o, question)));

  const questionReviewPanel = renderReviewerSlotBlock({
    scope: "question", blueprintId: question.blueprint_id, roleId: null, review: question.review,
  });

  return el("div", { class: "question-card" }, [
    meta,
    el("div", { class: "question-text", text: question.question_text }),
    traitPanel,
    questionReviewPanel,
    optionList,
  ]);
}

function renderCurrentQuestion() {
  const container = document.getElementById("question-container");
  container.replaceChildren();
  const q = state.questions[state.currentIndex];
  if (!q) {
    container.appendChild(el("p", { text: "표시할 질문이 없습니다(필터를 확인하세요)." }));
    return;
  }
  container.appendChild(renderQuestionCard(q));

  const visible = filteredQuestions();
  const pos = visible.indexOf(q);
  document.getElementById("pager-label").textContent = visible.length
    ? `${pos + 1} / ${visible.length} (전체 ${state.questions.length}개 중)`
    : "필터 결과 없음";
  document.getElementById("prev-btn").disabled = pos <= 0;
  document.getElementById("next-btn").disabled = pos === -1 || pos >= visible.length - 1;
}

/* ---- 2.5단계 §10: Context Routing 탭 전용 렌더링/로딩 ---- */

async function loadRoutingAll() {
  setSaveIndicator("Routing 불러오는 중…", "");
  const resp = await apiGet(`${API_BASE}/routing-questions`);
  state.routingQuestions = resp.questions;
  state.routingQuestionRevision = resp.question_review_revision;
  state.routingOptionRevision = resp.option_review_revision;
  renderRoutingSidebarList();
  renderCurrentRoutingQuestion();
  setSaveIndicator("불러옴", "saved");
}

async function refreshRoutingAfterSave() {
  const resp = await apiGet(`${API_BASE}/routing-questions`);
  const currentBlueprintId = state.routingQuestions[state.routingCurrentIndex]
    ? state.routingQuestions[state.routingCurrentIndex].blueprint_id : null;
  state.routingQuestions = resp.questions;
  state.routingQuestionRevision = resp.question_review_revision;
  state.routingOptionRevision = resp.option_review_revision;
  if (currentBlueprintId) {
    const idx = state.routingQuestions.findIndex((q) => q.blueprint_id === currentBlueprintId);
    if (idx !== -1) state.routingCurrentIndex = idx;
  }
  renderRoutingSidebarList();
  renderCurrentRoutingQuestion();
}

async function reloadRoutingAfterConflict() {
  if (state.dirty) {
    const proceed = confirm("저장하지 않은 변경사항이 있습니다. 새로고침하면 사라집니다. 계속할까요?");
    if (!proceed) return;
  }
  state.dirty = false;
  await loadRoutingAll();
}

function goToRoutingIndex(index) {
  if (!confirmDiscardIfDirty()) return;
  state.routingCurrentIndex = index;
  renderRoutingSidebarList();
  renderCurrentRoutingQuestion();
}

function stepRoutingQuestion(delta) {
  if (state.routingQuestions.length === 0) return;
  const next = Math.min(Math.max(state.routingCurrentIndex + delta, 0), state.routingQuestions.length - 1);
  goToRoutingIndex(next);
}

function renderRoutingSidebarList() {
  const list = document.getElementById("routing-nav-list");
  list.replaceChildren();
  state.routingQuestions.forEach((q, idx) => {
    const item = el(
      "li",
      { class: idx === state.routingCurrentIndex ? "current" : "", onclick: () => goToRoutingIndex(idx) },
      [el("span", { text: q.context_label }), statusPill(q.review.final_status)],
    );
    list.appendChild(item);
  });
}

function renderRoutingOptionCard(option, question) {
  const anchorChip = el("span", { class: "routing-anchor-chip", text: option.anchor_label });
  const meta = el("div", { class: "option-meta" }, [
    el("span", { text: `role_id: ${option.role_id}` }),
    anchorChip,
    el("span", { class: "mapping-only-inline", text: ` context_anchor: ${option.context_anchor}` }),
  ]);
  const reviewPanel = renderReviewerSlotBlock({
    scope: "option", blueprintId: question.blueprint_id, roleId: option.role_id, review: option.review,
    kind: "routing",
  });
  return el("li", { class: "option-card" }, [
    el("div", { class: "option-text", text: `${option.display_order}. ${option.text}` }),
    meta,
    reviewPanel,
  ]);
}

/* 2.5.1단계 §11 — Anchor Preview 패널. 실제 Runtime 함수(seed_question_as_finalized)를
 * 그대로 호출한 서버 결과만 렌더링한다 — 여기서 질문 문구를 스스로 만들지 않는다. */
function renderAnchorPreviewPanel(question) {
  const panel = el("div", { class: "anchor-preview-panel" }, [
    el("h4", {}, "Anchor Preview — 실제 첫 후속 질문 미리보기"),
    el("div", { class: "anchor-preview-buttons" },
      question.options.map((o) =>
        el("button", {
          type: "button", class: "anchor-preview-btn",
          onclick: () => loadAnchorPreview(question.context_id, o.context_anchor, resultBox),
        }, o.anchor_label)
      ),
    ),
  ]);
  const resultBox = el("div", { class: "anchor-preview-result" }, "위에서 Anchor를 선택하면 실제 첫 후속 질문이 여기 표시됩니다.");
  panel.appendChild(resultBox);
  return panel;
}

async function loadAnchorPreview(contextId, anchorId, resultBox) {
  resultBox.replaceChildren(el("p", {}, "불러오는 중…"));
  try {
    const preview = await apiGet(
      `${API_BASE}/anchor-preview?context_id=${encodeURIComponent(contextId)}&anchor_id=${encodeURIComponent(anchorId)}`,
    );
    resultBox.replaceChildren(
      el("div", {}, [el("strong", {}, `선택한 Anchor: ${preview.anchor_label} (${preview.anchor_id})`)]),
      el("div", {}, `선호 장면: ${preview.preferred_scenarios.join(", ") || "-"}`),
      el("div", {}, `금지 전제: ${preview.forbidden_assumptions.join(", ") || "(없음)"}`),
      el("div", { class: "question-text" }, preview.preview_question_text),
      el("ul", { class: "option-list" }, preview.preview_options.map((o) =>
        el("li", { class: "option-card" }, [
          el("div", { class: "option-text" }, o.text),
          el("div", { class: "option-meta" }, [
            el("span", {}, `role_id: ${o.role_id}`),
            el("span", {}, `공통 Trait Mapping: ${JSON.stringify(o.primary_trait_delta)}`),
          ]),
        ])
      )),
    );
  } catch (err) {
    resultBox.replaceChildren(el("p", { class: "inline-msg err" }, `Preview 실패: ${err.message}`));
  }
}

function renderRoutingQuestionCard(question) {
  const meta = el("div", { class: "meta" }, [
    el("span", { class: "student-hint", text: `Context: ${question.context_label}` }),
    el("span", { class: "mapping-only-inline", text: ` · blueprint_id: ${question.blueprint_id} · context_id: ${question.context_id}` }),
  ]);

  // Trait Mapping을 보여주지 않는다(§10) — 구조적으로 이미 보장된 사실만 확인 정보로
  // 보여주고, 나머지는 사람이 직접 판단하는 체크리스트로 남긴다.
  const guaranteePanel = el("div", { class: "trait-panel mapping-only" }, [
    el("div", {}, [
      question.trait_signal_free
        ? el("span", { class: "routing-check-ok", text: "✓ Trait Signal 없음(구조적으로 보장됨 — 이 질문의 답변은 어떤 Trait 점수에도 반영되지 않는다)" })
        : el("span", { class: "routing-check-manual", text: "⚠ Trait Signal 존재 — 확인 필요" }),
    ]),
    el("div", {}, [
      el("span", { text: `하위 Context(Anchor) ${question.distinct_anchor_count} / ${question.total_anchor_count}개가 서로 구분됨` }),
    ]),
  ]);

  const optionList = el("ul", { class: "option-list" }, question.options.map((o) => renderRoutingOptionCard(o, question)));

  const questionReviewPanel = renderReviewerSlotBlock({
    scope: "question", blueprintId: question.blueprint_id, roleId: null, review: question.review,
    kind: "routing",
  });

  return el("div", { class: "question-card" }, [
    meta,
    el("div", { class: "question-text", text: question.question_text }),
    guaranteePanel,
    renderAnchorPreviewPanel(question),
    questionReviewPanel,
    optionList,
  ]);
}

function renderCurrentRoutingQuestion() {
  const container = document.getElementById("question-container");
  container.replaceChildren();
  const q = state.routingQuestions[state.routingCurrentIndex];
  if (!q) {
    container.appendChild(el("p", { text: "표시할 Routing 질문이 없습니다." }));
    return;
  }
  container.appendChild(renderRoutingQuestionCard(q));

  document.getElementById("pager-label").textContent =
    `${state.routingCurrentIndex + 1} / ${state.routingQuestions.length}`;
  document.getElementById("prev-btn").disabled = state.routingCurrentIndex <= 0;
  document.getElementById("next-btn").disabled = state.routingCurrentIndex >= state.routingQuestions.length - 1;
}

/* ---- 2.5.2단계 §12: Seed Anchor Variant 탭 전용 렌더링/로딩 ---- */

async function loadSeedAnchorAll() {
  setSaveIndicator("Seed Anchor Variant 불러오는 중…", "");
  const resp = await apiGet(`${API_BASE}/seed-anchor-questions`);
  state.seedAnchorQuestions = resp.questions;
  state.seedAnchorQuestionRevision = resp.question_review_revision;
  state.seedAnchorOptionRevision = resp.option_review_revision;
  renderSeedAnchorSidebarList();
  renderCurrentSeedAnchorQuestion();
  setSaveIndicator("불러옴", "saved");
}

async function refreshSeedAnchorAfterSave() {
  const resp = await apiGet(`${API_BASE}/seed-anchor-questions`);
  const current = state.seedAnchorQuestions[state.seedAnchorCurrentIndex];
  const currentKey = current ? `${current.context_id}:${current.anchor_id}` : null;
  state.seedAnchorQuestions = resp.questions;
  state.seedAnchorQuestionRevision = resp.question_review_revision;
  state.seedAnchorOptionRevision = resp.option_review_revision;
  if (currentKey) {
    const idx = state.seedAnchorQuestions.findIndex((q) => `${q.context_id}:${q.anchor_id}` === currentKey);
    if (idx !== -1) state.seedAnchorCurrentIndex = idx;
  }
  renderSeedAnchorSidebarList();
  renderCurrentSeedAnchorQuestion();
}

async function reloadSeedAnchorAfterConflict() {
  if (state.dirty) {
    const proceed = confirm("저장하지 않은 변경사항이 있습니다. 새로고침하면 사라집니다. 계속할까요?");
    if (!proceed) return;
  }
  state.dirty = false;
  await loadSeedAnchorAll();
}

function goToSeedAnchorIndex(index) {
  if (!confirmDiscardIfDirty()) return;
  state.seedAnchorCurrentIndex = index;
  renderSeedAnchorSidebarList();
  renderCurrentSeedAnchorQuestion();
}

function stepSeedAnchorQuestion(delta) {
  if (state.seedAnchorQuestions.length === 0) return;
  const next = Math.min(Math.max(state.seedAnchorCurrentIndex + delta, 0), state.seedAnchorQuestions.length - 1);
  goToSeedAnchorIndex(next);
}

function renderSeedAnchorSidebarList() {
  const list = document.getElementById("seed-anchor-nav-list");
  list.replaceChildren();
  state.seedAnchorQuestions.forEach((q, idx) => {
    const item = el(
      "li",
      { class: idx === state.seedAnchorCurrentIndex ? "current" : "", onclick: () => goToSeedAnchorIndex(idx) },
      [el("span", { text: `${q.context_label} · ${q.anchor_label}` }), statusPill(q.review.final_status)],
    );
    list.appendChild(item);
  });
}

function renderSeedAnchorOptionCard(option, question) {
  const mappingDetails = el("div", { class: "mapping-only" }, [
    el("div", { class: "option-meta" }, [
      el("span", { text: `role_id: ${option.role_id}` }),
      el("span", { text: `Trait: ${option.trait_label} (${option.trait_id})` }),
    ]),
    el("div", { class: "def" }, option.trait_definition),
    el("div", { class: "mapping-rationale-draft" }, `Mapping Rationale Draft(팀 초안, 검증 완료 아님): ${option.mapping_rationale_draft}`),
    el("div", { class: "neutral-comparison" }, `중립 Seed 선택지: ${option.neutral_text}`),
  ]);

  const reviewPanel = renderReviewerSlotBlock({
    scope: "option", blueprintId: `${encodeURIComponent(question.context_id)}/${encodeURIComponent(question.anchor_id)}`,
    roleId: option.role_id, review: option.review, kind: "seed_anchor",
  });

  return el("li", { class: "option-card" }, [
    el("div", { class: "option-text", text: option.text }),
    mappingDetails,
    reviewPanel,
  ]);
}

function renderSeedAnchorQuestionCard(question) {
  const meta = el("div", { class: "meta" }, [
    el("span", { class: "student-hint", text: `Context: ${question.context_label}` }),
    el("span", { class: "mapping-only-inline", text: ` · anchor_id: ${question.anchor_id} · anchor_label: ${question.anchor_label}` }),
  ]);

  const neutralPanel = el("div", { class: "neutral-comparison mapping-only" }, `중립 Seed 질문: ${question.neutral_question_text}`);

  const optionList = el("ul", { class: "option-list" }, question.options.map((o) => renderSeedAnchorOptionCard(o, question)));

  const questionReviewPanel = renderReviewerSlotBlock({
    scope: "question", blueprintId: `${encodeURIComponent(question.context_id)}/${encodeURIComponent(question.anchor_id)}`,
    roleId: null, review: question.review, kind: "seed_anchor",
  });

  return el("div", { class: "question-card" }, [
    meta,
    el("div", { class: "question-text", text: question.question_text }),
    neutralPanel,
    questionReviewPanel,
    optionList,
  ]);
}

function renderCurrentSeedAnchorQuestion() {
  const container = document.getElementById("question-container");
  container.replaceChildren();
  const q = state.seedAnchorQuestions[state.seedAnchorCurrentIndex];
  if (!q) {
    container.appendChild(el("p", { text: "표시할 Seed Anchor Variant 질문이 없습니다." }));
    return;
  }
  container.appendChild(renderSeedAnchorQuestionCard(q));

  document.getElementById("pager-label").textContent =
    `${state.seedAnchorCurrentIndex + 1} / ${state.seedAnchorQuestions.length}`;
  document.getElementById("prev-btn").disabled = state.seedAnchorCurrentIndex <= 0;
  document.getElementById("next-btn").disabled = state.seedAnchorCurrentIndex >= state.seedAnchorQuestions.length - 1;
}

/* ---- 2.5.3단계 §11: Backup Question 탭 전용 렌더링/로딩 ---- */

async function loadBackupAll() {
  setSaveIndicator("Backup Question 불러오는 중…", "");
  const resp = await apiGet(`${API_BASE}/backup-questions`);
  state.backupQuestions = resp.questions;
  state.backupQuestionRevision = resp.question_review_revision;
  state.backupOptionRevision = resp.option_review_revision;
  renderBackupSidebarList();
  renderCurrentBackupQuestion();
  setSaveIndicator("불러옴", "saved");
}

async function refreshBackupAfterSave() {
  const resp = await apiGet(`${API_BASE}/backup-questions`);
  const current = state.backupQuestions[state.backupCurrentIndex];
  const currentId = current ? current.question_id : null;
  state.backupQuestions = resp.questions;
  state.backupQuestionRevision = resp.question_review_revision;
  state.backupOptionRevision = resp.option_review_revision;
  if (currentId) {
    const idx = state.backupQuestions.findIndex((q) => q.question_id === currentId);
    if (idx !== -1) state.backupCurrentIndex = idx;
  }
  renderBackupSidebarList();
  renderCurrentBackupQuestion();
}

async function reloadBackupAfterConflict() {
  if (state.dirty) {
    const proceed = confirm("저장하지 않은 변경사항이 있습니다. 새로고침하면 사라집니다. 계속할까요?");
    if (!proceed) return;
  }
  state.dirty = false;
  await loadBackupAll();
}

function goToBackupIndex(index) {
  if (!confirmDiscardIfDirty()) return;
  state.backupCurrentIndex = index;
  renderBackupSidebarList();
  renderCurrentBackupQuestion();
}

function stepBackupQuestion(delta) {
  if (state.backupQuestions.length === 0) return;
  const next = Math.min(Math.max(state.backupCurrentIndex + delta, 0), state.backupQuestions.length - 1);
  goToBackupIndex(next);
}

function renderBackupSidebarList() {
  const list = document.getElementById("backup-nav-list");
  list.replaceChildren();
  state.backupQuestions.forEach((q, idx) => {
    const item = el(
      "li",
      { class: idx === state.backupCurrentIndex ? "current" : "", onclick: () => goToBackupIndex(idx) },
      [el("span", { text: `${q.context_label} · ${q.question_id}` }), statusPill(q.review.final_status)],
    );
    list.appendChild(item);
  });
}

function renderBackupOptionCard(option, question) {
  const mappingDetails = el("div", { class: "mapping-only" }, [
    el("div", { class: "option-meta" }, [
      el("span", { text: `role_id: ${option.role_id}` }),
      el("span", { text: `Trait: ${option.trait_label} (${option.trait_id})` }),
    ]),
    el("div", { class: "def" }, option.trait_definition),
    el("div", { class: "mapping-rationale-draft" }, `Mapping Rationale Draft(팀 초안, 검증 완료 아님): ${option.mapping_rationale_draft}`),
  ]);

  const reviewPanel = renderReviewerSlotBlock({
    scope: "option", blueprintId: question.question_id, roleId: option.role_id, review: option.review,
    kind: "backup",
  });

  return el("li", { class: "option-card" }, [
    el("div", { class: "option-text", text: option.text }),
    mappingDetails,
    reviewPanel,
  ]);
}

/* 실제 Runtime의 check_backup_candidate()를 그대로 호출하는 서버 결과만 렌더링한다. */
async function loadBackupAnchorPreview(question, anchorId, resultBox) {
  resultBox.replaceChildren(el("p", {}, "불러오는 중…"));
  try {
    const params = new URLSearchParams({ context_id: question.context_id });
    if (anchorId) params.set("anchor_id", anchorId);
    const preview = await apiGet(`${API_BASE}/backup-questions/${encodeURIComponent(question.question_id)}/anchor-preview?${params}`);
    resultBox.replaceChildren(
      el("div", {}, [
        el("strong", {}, `Anchor: ${anchorId || "(없음 — 중립 요청)"}`),
        el("span", { class: `routing-check-${preview.passed ? "ok" : "manual"}`, text: preview.passed ? " ✓ 사용 가능" : " ✗ 거부됨" }),
      ]),
      preview.failures.length
        ? el("ul", {}, preview.failures.map((f) => el("li", {}, f)))
        : null,
    );
  } catch (err) {
    resultBox.replaceChildren(el("p", { class: "inline-msg err" }, `Preview 실패: ${err.message}`));
  }
}

function renderBackupAnchorPreviewPanel(question) {
  const resultBox = el("div", { class: "anchor-preview-result" }, "위에서 Anchor를 선택하면 실제 적합성 검사 결과가 여기 표시됩니다.");
  const anchorIds = Object.keys(question.anchor_gate_results).filter((k) => k !== "neutral");
  const panel = el("div", { class: "anchor-preview-panel" }, [
    el("h4", {}, "Anchor Preview — 실제 Backup 적합성 검사"),
    el("div", { class: "anchor-preview-buttons" }, [
      el("button", { type: "button", class: "anchor-preview-btn", onclick: () => loadBackupAnchorPreview(question, null, resultBox) }, "중립(Anchor 없음)"),
      ...anchorIds.map((anchorId) =>
        el("button", { type: "button", class: "anchor-preview-btn", onclick: () => loadBackupAnchorPreview(question, anchorId, resultBox) }, anchorId)
      ),
    ]),
  ]);
  panel.appendChild(resultBox);
  return panel;
}

function renderBackupQuestionCard(question) {
  const meta = el("div", { class: "meta" }, [
    el("span", { class: "student-hint", text: `Context: ${question.context_label}` }),
    el("span", { class: "mapping-only-inline", text: ` · question_id: ${question.question_id}` }),
  ]);

  const gateGrid = el("div", { class: "anchor-gate-grid mapping-only" },
    Object.entries(question.anchor_gate_results).map(([anchorId, passed]) =>
      el("span", { class: `anchor-gate-chip ${passed ? "pass" : "fail"}`, text: `${anchorId}: ${passed ? "통과" : "거부"}` })
    ),
  );

  const applicabilityPanel = el("div", { class: "neutral-comparison mapping-only" }, [
    el("div", {}, `허용 Anchor: ${question.allowed_anchor_ids ? question.allowed_anchor_ids.join(", ") : "전체(중립)"}`),
    el("div", {}, `제외 Anchor: ${question.excluded_anchor_ids.length ? question.excluded_anchor_ids.join(", ") : "(없음)"}`),
    el("div", { class: "mapping-rationale-draft" }, `Applicability 초안(검증 완료 아님): ${question.applicability_reason_draft}`),
  ]);

  const optionList = el("ul", { class: "option-list" }, question.options.map((o) => renderBackupOptionCard(o, question)));

  const questionReviewPanel = renderReviewerSlotBlock({
    scope: "question", blueprintId: question.question_id, roleId: null, review: question.review, kind: "backup",
  });

  return el("div", { class: "question-card" }, [
    meta,
    el("div", { class: "question-text", text: question.question_text }),
    gateGrid,
    applicabilityPanel,
    renderBackupAnchorPreviewPanel(question),
    questionReviewPanel,
    optionList,
  ]);
}

function renderCurrentBackupQuestion() {
  const container = document.getElementById("question-container");
  container.replaceChildren();
  const q = state.backupQuestions[state.backupCurrentIndex];
  if (!q) {
    container.appendChild(el("p", { text: "표시할 Backup 질문이 없습니다." }));
    return;
  }
  container.appendChild(renderBackupQuestionCard(q));

  document.getElementById("pager-label").textContent =
    `${state.backupCurrentIndex + 1} / ${state.backupQuestions.length}`;
  document.getElementById("prev-btn").disabled = state.backupCurrentIndex <= 0;
  document.getElementById("next-btn").disabled = state.backupCurrentIndex >= state.backupQuestions.length - 1;
}

/* ---- 2.5.4단계 §7: Anchor Backup 탭 전용 렌더링/로딩(기존 Backup 탭과 완전히 분리) ---- */

async function loadAnchorBackupAll() {
  setSaveIndicator("Anchor Backup 불러오는 중…", "");
  const resp = await apiGet(`${API_BASE}/anchor-backup-questions`);
  state.anchorBackupQuestions = resp.questions;
  state.anchorBackupQuestionRevision = resp.question_review_revision;
  state.anchorBackupOptionRevision = resp.option_review_revision;
  renderAnchorBackupSidebarList();
  renderCurrentAnchorBackupQuestion();
  setSaveIndicator("불러옴", "saved");
}

async function refreshAnchorBackupAfterSave() {
  const resp = await apiGet(`${API_BASE}/anchor-backup-questions`);
  const current = state.anchorBackupQuestions[state.anchorBackupCurrentIndex];
  const currentId = current ? current.question_id : null;
  state.anchorBackupQuestions = resp.questions;
  state.anchorBackupQuestionRevision = resp.question_review_revision;
  state.anchorBackupOptionRevision = resp.option_review_revision;
  if (currentId) {
    const idx = state.anchorBackupQuestions.findIndex((q) => q.question_id === currentId);
    if (idx !== -1) state.anchorBackupCurrentIndex = idx;
  }
  renderAnchorBackupSidebarList();
  renderCurrentAnchorBackupQuestion();
}

async function reloadAnchorBackupAfterConflict() {
  if (state.dirty) {
    const proceed = confirm("저장하지 않은 변경사항이 있습니다. 새로고침하면 사라집니다. 계속할까요?");
    if (!proceed) return;
  }
  state.dirty = false;
  await loadAnchorBackupAll();
}

function goToAnchorBackupIndex(index) {
  if (!confirmDiscardIfDirty()) return;
  state.anchorBackupCurrentIndex = index;
  renderAnchorBackupSidebarList();
  renderCurrentAnchorBackupQuestion();
}

function stepAnchorBackupQuestion(delta) {
  if (state.anchorBackupQuestions.length === 0) return;
  const next = Math.min(Math.max(state.anchorBackupCurrentIndex + delta, 0), state.anchorBackupQuestions.length - 1);
  goToAnchorBackupIndex(next);
}

function renderAnchorBackupSidebarList() {
  const list = document.getElementById("anchor-backup-nav-list");
  list.replaceChildren();
  state.anchorBackupQuestions.forEach((q, idx) => {
    const item = el(
      "li",
      { class: idx === state.anchorBackupCurrentIndex ? "current" : "", onclick: () => goToAnchorBackupIndex(idx) },
      [el("span", { text: `${q.context_label} · ${q.question_id}` }), statusPill(q.review.final_status)],
    );
    list.appendChild(item);
  });
}

function renderAnchorBackupOptionCard(option, question) {
  const mappingDetails = el("div", { class: "mapping-only" }, [
    el("div", { class: "option-meta" }, [
      el("span", { text: `role_id: ${option.role_id}` }),
      el("span", { text: option.trait_id ? `Trait: ${option.trait_label} (${option.trait_id})` : "NO_SIGNAL" }),
    ]),
    option.trait_definition ? el("div", { class: "def" }, option.trait_definition) : null,
    el("div", { class: "mapping-rationale-draft" }, `Mapping Rationale Draft(팀 초안, 검증 완료 아님): ${option.mapping_rationale_draft}`),
  ]);

  const reviewPanel = renderReviewerSlotBlock({
    scope: "option", blueprintId: question.question_id, roleId: option.role_id, review: option.review,
    kind: "anchor_backup",
  });

  return el("li", { class: "option-card" }, [
    el("div", { class: "option-text", text: option.text }),
    mappingDetails,
    reviewPanel,
  ]);
}

async function loadAnchorBackupAnchorPreview(question, anchorId, resultBox) {
  resultBox.replaceChildren(el("p", {}, "불러오는 중…"));
  try {
    const params = new URLSearchParams({ context_id: question.context_id });
    if (anchorId) params.set("anchor_id", anchorId);
    const preview = await apiGet(`${API_BASE}/anchor-backup-questions/${encodeURIComponent(question.question_id)}/anchor-preview?${params}`);
    resultBox.replaceChildren(
      el("div", {}, [
        el("strong", {}, `Anchor: ${anchorId || "(없음 — 중립 요청)"}`),
        el("span", { class: `routing-check-${preview.passed ? "ok" : "manual"}`, text: preview.passed ? " ✓ 사용 가능" : " ✗ 거부됨" }),
      ]),
      preview.failures.length
        ? el("ul", {}, preview.failures.map((f) => el("li", {}, f)))
        : null,
    );
  } catch (err) {
    resultBox.replaceChildren(el("p", { class: "inline-msg err" }, `Preview 실패: ${err.message}`));
  }
}

function renderAnchorBackupAnchorPreviewPanel(question) {
  const resultBox = el("div", { class: "anchor-preview-result" }, "위에서 Anchor를 선택하면 실제 적합성 검사 결과가 여기 표시됩니다.");
  const anchorIds = Object.keys(question.anchor_gate_results).filter((k) => k !== "neutral");
  const panel = el("div", { class: "anchor-preview-panel" }, [
    el("h4", {}, "Anchor Preview — 실제 Backup 적합성 검사"),
    el("div", { class: "anchor-preview-buttons" }, [
      el("button", { type: "button", class: "anchor-preview-btn", onclick: () => loadAnchorBackupAnchorPreview(question, null, resultBox) }, "중립(Anchor 없음)"),
      ...anchorIds.map((anchorId) =>
        el("button", { type: "button", class: "anchor-preview-btn", onclick: () => loadAnchorBackupAnchorPreview(question, anchorId, resultBox) }, anchorId)
      ),
    ]),
  ]);
  panel.appendChild(resultBox);
  return panel;
}

function renderAnchorBackupQuestionCard(question) {
  const meta = el("div", { class: "meta" }, [
    el("span", { class: "student-hint", text: `Context: ${question.context_label}` }),
    el("span", { class: "mapping-only-inline", text: ` · question_id: ${question.question_id}` }),
  ]);

  const gateGrid = el("div", { class: "anchor-gate-grid mapping-only" },
    Object.entries(question.anchor_gate_results).map(([anchorId, passed]) =>
      el("span", { class: `anchor-gate-chip ${passed ? "pass" : "fail"}`, text: `${anchorId}: ${passed ? "통과" : "거부"}` })
    ),
  );

  const applicabilityPanel = el("div", { class: "neutral-comparison mapping-only" }, [
    el("div", {}, `허용 Anchor: ${question.allowed_anchor_ids ? question.allowed_anchor_ids.join(", ") : "전체(중립)"}`),
    el("div", {}, `제외 Anchor: ${question.excluded_anchor_ids.length ? question.excluded_anchor_ids.join(", ") : "(없음)"}`),
    el("div", { class: "mapping-rationale-draft" }, `Applicability 초안(검증 완료 아님): ${question.applicability_reason_draft}`),
  ]);

  // §2/§7 — 이전 REVISE Backup과의 관계.
  const supersedesPanel = el("div", { class: "neutral-comparison mapping-only" },
    `대체 대상(v2 Runtime에서 제외된 기존 REVISE Backup): ${question.superseded_question_ids.length ? question.superseded_question_ids.join(", ") : "(없음)"}`,
  );

  const optionList = el("ul", { class: "option-list" }, question.options.map((o) => renderAnchorBackupOptionCard(o, question)));

  const questionReviewPanel = renderReviewerSlotBlock({
    scope: "question", blueprintId: question.question_id, roleId: null, review: question.review, kind: "anchor_backup",
  });

  return el("div", { class: "question-card" }, [
    meta,
    el("div", { class: "question-text", text: question.question_text }),
    gateGrid,
    applicabilityPanel,
    supersedesPanel,
    renderAnchorBackupAnchorPreviewPanel(question),
    questionReviewPanel,
    optionList,
  ]);
}

function renderCurrentAnchorBackupQuestion() {
  const container = document.getElementById("question-container");
  container.replaceChildren();
  const q = state.anchorBackupQuestions[state.anchorBackupCurrentIndex];
  if (!q) {
    container.appendChild(el("p", { text: "표시할 Anchor Backup 질문이 없습니다." }));
    return;
  }
  container.appendChild(renderAnchorBackupQuestionCard(q));

  document.getElementById("pager-label").textContent =
    `${state.anchorBackupCurrentIndex + 1} / ${state.anchorBackupQuestions.length}`;
  document.getElementById("prev-btn").disabled = state.anchorBackupCurrentIndex <= 0;
  document.getElementById("next-btn").disabled = state.anchorBackupCurrentIndex >= state.anchorBackupQuestions.length - 1;
}

/* ---- 2026-08-24 2.9.1단계 §5 + 2026-08-24 배치별 검수: ContextPack 공용
 * Adaptive Probe 탭 ----
 *
 * 실제 Runtime 변환 함수(ContextPackRegistry.is_shared_probe_approved_for_anchor,
 * run_quality_gate)를 그대로 호출한 값만 보여준다 — 이 파일이 직접 승인 여부나
 * forbidden assumption 결과를 계산하지 않는다(서버 응답을 그대로 렌더링할 뿐이다).
 * 이 탭은 어떤 항목도 자동으로 APPROVE하지 않는다 — 사람이 체크박스로 고른 Anchor
 * 목록만 그대로 서버에 보낸다.
 *
 * 14개 Probe × 12개 Context × 5개 Anchor(최대 840개 판단)를 한 화면에 다 보여주면
 * 1차 배치(business/science/sports)만 검수하기 어렵다 — 배치 필터(activation_batch,
 * 서버가 CONTEXT_ACTIVATION_BATCHES에서 그대로 계산해 내려준 값)로 Context 행을
 * 좁히고, 상태 필터로 "아직 손대지 않은 것"부터 보이게 한다. 두 필터 모두 이미
 * 저장된 서버 데이터를 걸러 보여줄 뿐 — 필터를 바꾼다고 서버 상태가 바뀌지 않는다. */

function sharedProbeContextRowMatchesBatch(row) {
  if (state.sharedProbeBatch === "all") return true;
  return row.activation_batch === state.sharedProbeBatch;
}

function sharedProbeContextRowMatchesStatusFilter(row) {
  switch (state.sharedProbeStatusFilter) {
    case "all":
      return true;
    case "TBD":
    case "APPROVE":
    case "REVISE":
    case "HOLD":
      return row.review.reviewer_1_status === state.sharedProbeStatusFilter;
    case "anchor_undetermined":
      return row.anchors.some((a) => !a.is_approved && !a.is_excluded);
    case "runtime_usable":
      return row.is_runtime_usable === true;
    case "runtime_unusable":
      return row.is_runtime_usable === false;
    default:
      return true;
  }
}

function sharedProbeVisibleContextRows(probe) {
  return probe.contexts.filter((row) => sharedProbeContextRowMatchesBatch(row) && sharedProbeContextRowMatchesStatusFilter(row));
}

function sharedProbeBatchContextRows(probe) {
  return probe.contexts.filter((row) => sharedProbeContextRowMatchesBatch(row));
}

/* §5 진행 현황 — Context 3개 × Probe 14개 같은 배치 전체 범위(상태 필터 무관)와,
 * 그 범위 안 Context-Probe 검수 완료 수 / Anchor 승인·제외·미판정 수를 실제 서버
 * 응답을 그대로 집계해서 계산한다(이 함수가 뭔가를 판정하지 않는다 — 세는 것뿐). */
function computeSharedProbeBatchStats() {
  const contextIdSet = new Set();
  let totalPairs = 0;
  let completedPairs = 0;
  let approvedAnchors = 0;
  let excludedAnchors = 0;
  let undeterminedAnchors = 0;
  const perContext = new Map();
  state.sharedProbes.forEach((probe) => {
    sharedProbeBatchContextRows(probe).forEach((row) => {
      contextIdSet.add(row.context_id);
      totalPairs += 1;
      if (row.review.reviewer_1_status !== "TBD") completedPairs += 1;
      if (!perContext.has(row.context_id)) perContext.set(row.context_id, { approved: 0, excluded: 0, undetermined: 0 });
      const bucket = perContext.get(row.context_id);
      row.anchors.forEach((a) => {
        if (a.is_approved) {
          approvedAnchors += 1;
          bucket.approved += 1;
        } else if (a.is_excluded) {
          excludedAnchors += 1;
          bucket.excluded += 1;
        } else {
          undeterminedAnchors += 1;
          bucket.undetermined += 1;
        }
      });
    });
  });
  return {
    contextIds: [...contextIdSet].sort(), probeCount: state.sharedProbes.length,
    totalPairs, completedPairs, approvedAnchors, excludedAnchors, undeterminedAnchors, perContext,
  };
}

async function loadSharedProbesAll() {
  const resp = await apiGet(`${API_BASE}/context-packs/shared-probes`);
  state.sharedProbes = resp.probes;
  if (state.sharedProbeCurrentBlueprintId == null && state.sharedProbes.length > 0) {
    state.sharedProbeCurrentBlueprintId = state.sharedProbes[0].blueprint_id;
  }
  renderSharedProbeBatchSelector();
  renderSharedProbeProgressDashboard();
  renderSharedProbesSidebarList();
  renderCurrentSharedProbe();
}

function selectSharedProbeBatch(batchNo, opts) {
  const options = opts || {};
  state.sharedProbeBatch = batchNo;
  if (!options.skipHashSync) syncHash();
  renderSharedProbeBatchSelector();
  renderSharedProbeProgressDashboard();
  renderSharedProbesSidebarList();
  renderCurrentSharedProbe();
}

function renderSharedProbeBatchSelector() {
  const box = document.getElementById("shared-probe-batch-selector");
  if (!box) return;
  box.replaceChildren();
  // 배치 번호 목록은 실제 응답에 나타난 activation_batch 값에서만 뽑는다(하드코딩
  // 없음) — 서버 정본이 바뀌면 그대로 따라간다.
  const batchNumbers = [
    ...new Set(state.sharedProbes.flatMap((p) => p.contexts.map((c) => c.activation_batch)).filter((b) => b != null)),
  ].sort((a, b) => a - b);
  batchNumbers.forEach((n) => {
    box.appendChild(
      el("button", {
        type: "button", class: n === state.sharedProbeBatch ? "active" : "",
        onclick: () => selectSharedProbeBatch(n),
      }, CONTEXTPACK_BATCH_LABEL[n] || `배치 ${n}`),
    );
  });
  box.appendChild(
    el("button", {
      type: "button", class: state.sharedProbeBatch === "all" ? "active" : "",
      onclick: () => selectSharedProbeBatch("all"),
    }, "전체"),
  );
}

function renderSharedProbeProgressDashboard() {
  const box = document.getElementById("shared-probe-progress-dashboard");
  if (!box) return;
  box.replaceChildren();
  const stats = computeSharedProbeBatchStats();
  const batchLabel = state.sharedProbeBatch === "all" ? "전체" : CONTEXTPACK_BATCH_LABEL[state.sharedProbeBatch] || `배치 ${state.sharedProbeBatch}`;
  box.appendChild(el("div", { class: "row" }, [el("strong", { text: batchLabel }), el("span", { class: "n", text: `Context ${stats.contextIds.length}개` })]));
  box.appendChild(el("div", { class: "row" }, [el("span", { text: "Shared Probe" }), el("span", { class: "n", text: `${stats.probeCount}개` })]));
  box.appendChild(
    el("div", { class: "row" }, [el("span", { text: "Context–Probe 검수 완료" }), el("span", { class: "n", text: `${stats.completedPairs} / ${stats.totalPairs}` })]),
  );
  box.appendChild(el("div", { class: "row" }, [el("span", { text: "Anchor 승인" }), el("span", { class: "n", text: String(stats.approvedAnchors) })]));
  box.appendChild(el("div", { class: "row" }, [el("span", { text: "Anchor 제외" }), el("span", { class: "n", text: String(stats.excludedAnchors) })]));
  box.appendChild(el("div", { class: "row" }, [el("span", { text: "미판정 Anchor" }), el("span", { class: "n", text: String(stats.undeterminedAnchors) })]));
  box.appendChild(el("hr"));
  stats.contextIds.forEach((contextId) => {
    const bucket = stats.perContext.get(contextId);
    box.appendChild(
      el("div", { class: "context-row", text: `${contextId}: 승인 ${bucket.approved} / 제외 ${bucket.excluded} / 미판정 ${bucket.undetermined}` }),
    );
  });
}

function renderSharedProbesSidebarList() {
  const list = document.getElementById("shared-probe-nav-list");
  list.replaceChildren();
  state.sharedProbes.forEach((probe) => {
    const batchRows = sharedProbeBatchContextRows(probe);
    const approvedContexts = batchRows.filter((c) => c.is_runtime_usable).length;
    const item = el("li", {
      class: probe.blueprint_id === state.sharedProbeCurrentBlueprintId ? "active" : "",
      onclick: () => {
        state.sharedProbeCurrentBlueprintId = probe.blueprint_id;
        renderSharedProbesSidebarList();
        renderCurrentSharedProbe();
      },
    }, [
      el("div", { text: probe.blueprint_id }),
      el("div", { class: "meta", text: `${probe.trait_label} · 사용 가능 Context ${approvedContexts}/${batchRows.length}` }),
    ]);
    list.appendChild(item);
  });
}

function renderSharedProbeAnchorCard(probe, contextRow, anchor) {
  const approveBox = el("input", { type: "checkbox" });
  approveBox.checked = anchor.is_approved;
  const excludeBox = el("input", { type: "checkbox" });
  excludeBox.checked = anchor.is_excluded;

  // §7 — 승인·제외 상호배타. 한쪽을 켜면 다른 쪽을 끈다. 서버로는 저장 버튼을
  // 눌렀을 때만 이 두 체크박스의 현재 상태를 그대로 보낸다 — 여기서는 화면
  // 상태만 바꾼다(서버 상태는 저장 전까지 바뀌지 않는다).
  approveBox.addEventListener("change", () => {
    if (approveBox.checked) excludeBox.checked = false;
    markDirty();
  });
  excludeBox.addEventListener("change", () => {
    if (excludeBox.checked) approveBox.checked = false;
    markDirty();
  });

  const failureList = anchor.forbidden_assumption_failures.length
    ? el("ul", { class: "shared-probe-failure-list" }, anchor.forbidden_assumption_failures.map((f) => el("li", { text: f })))
    : el("div", { class: "routing-check-ok", text: "forbidden assumption 위반 없음" });

  const msg = el("span", { class: "inline-msg" });
  const saveAnchorBtn = el("button", { type: "button", text: "이 Anchor 판정 저장" });
  saveAnchorBtn.addEventListener("click", async () => {
    // approveBox/excludeBox가 change 리스너로 이미 상호배타를 강제하므로 이 시점에
    // 둘 다 true일 수 없다 — 그래도 방어적으로 한 번 더 배타 처리한다(교집합 없는
    // 목록만 서버로 보낸다 — 서버 Schema의 교집합 거부 규칙과 이중으로 맞춘다).
    const approved = approveBox.checked && !excludeBox.checked;
    const excluded = excludeBox.checked && !approveBox.checked;
    const approvedIds = new Set(contextRow.anchors.filter((a) => (a.anchor_id === anchor.anchor_id ? approved : a.is_approved)).map((a) => a.anchor_id));
    const excludedIds = new Set(contextRow.anchors.filter((a) => (a.anchor_id === anchor.anchor_id ? excluded : a.is_excluded)).map((a) => a.anchor_id));
    // 2026-08-24 2.9.1단계 §1-3: 이 버튼은 Anchor 목록만 바꾼다 — status/comment는
    // 아예 보내지 않는다(요청에서 생략 = 서버가 None으로 받아 기존 값 유지). 예전엔
    // 여기서 TBD를 "APPROVE"로 암묵적으로 승격시켜 보냈다 — Anchor 하나 승인이 곧
    // Context 전체 승인으로 새는 버그였다. Context의 reviewer_1_status는 아래
    // "Context 상태 저장" 버튼으로 사람이 select에서 명시적으로 고를 때만 바뀐다.
    await saveSharedProbeContextReview(
      probe.blueprint_id, contextRow.context_id,
      { approved_anchor_ids: Array.from(approvedIds), excluded_anchor_ids: Array.from(excludedIds) },
      { button: saveAnchorBtn, msg },
    );
  });

  return el("div", { class: "option-card" }, [
    el("div", { class: "option-text", text: `${anchor.label} (${anchor.anchor_id})` }),
    el("div", { class: "option-meta", text: `상황 표현: ${anchor.situation_terms.join(", ")}` }),
    el("div", { class: "option-meta", text: `선호 장면: ${anchor.preferred_scenarios.join(", ")}` }),
    el("div", { class: "option-meta", text: `금지 전제: ${anchor.forbidden_assumptions.join(", ") || "(없음)"}` }),
    failureList,
    el("label", { class: "shared-probe-anchor-toggle" }, [approveBox, " 이 Anchor 승인"]),
    el("label", { class: "shared-probe-anchor-toggle" }, [excludeBox, " 이 Anchor 제외"]),
    el("div", { class: "save-row" }, [saveAnchorBtn, msg]),
  ]);
}

function renderSharedProbeContextRow(probe, contextRow) {
  const commentBox = el("textarea", { rows: "2", placeholder: "사용자 메모" });
  commentBox.value = contextRow.review.reviewer_1_comment;

  const statusSelect = el("select", {}, ["TBD", "APPROVE", "REVISE", "HOLD"].map((s) => el("option", { value: s, text: s })));
  statusSelect.value = contextRow.review.reviewer_1_status;

  const msg = el("span", { class: "inline-msg" });
  const saveContextBtn = el("button", { type: "button", text: "Context 상태 저장" });
  saveContextBtn.addEventListener("click", async () => {
    // §8 — Anchor 목록은 명시적으로 null(=변경 안 함)을 보낸다. 이 버튼이 Anchor를
    // 자동 승인·제외하는 일이 절대 없다(회귀 테스트로 확인).
    await saveSharedProbeContextReview(
      probe.blueprint_id, contextRow.context_id,
      { status: statusSelect.value, comment: commentBox.value, approved_anchor_ids: null, excluded_anchor_ids: null },
      { button: saveContextBtn, msg },
    );
  });

  return el("div", { class: "question-card" }, [
    el("div", { class: "meta" }, [
      el("strong", { text: contextRow.context_label }),
      ` (${contextRow.context_id}, ${CONTEXTPACK_BATCH_LABEL[contextRow.activation_batch] || "배치 미지정"}) — `,
      statusPill(contextRow.review.final_status),
      contextRow.is_runtime_usable ? el("span", { class: "routing-check-ok", text: " · Runtime 사용 가능" }) : el("span", { class: "routing-check-manual", text: " · 아직 사용 불가(Anchor 미승인)" }),
    ]),
    el("div", {}, [statusSelect, saveContextBtn, msg]),
    commentBox,
    el("div", { class: "option-list" }, contextRow.anchors.map((a) => renderSharedProbeAnchorCard(probe, contextRow, a))),
  ]);
}

function renderCurrentSharedProbe() {
  const container = document.getElementById("shared-probe-container");
  container.replaceChildren();
  const probe = state.sharedProbes.find((p) => p.blueprint_id === state.sharedProbeCurrentBlueprintId);
  if (!probe) {
    container.appendChild(el("div", {}, "공용 Adaptive Probe가 없습니다."));
    return;
  }

  const traitPanel = el("div", { class: "trait-panel" }, [
    el("div", { text: `Trait: ${probe.trait_label} (${probe.trait_id})` }),
    el("div", { class: "def", text: probe.trait_definition }),
    el("div", { class: "mapping-rationale-draft", text: `Mapping Rationale(Blueprint purpose): ${probe.purpose}` }),
  ]);

  const optionList = el("ul", { class: "option-list" }, probe.options.map((o) => el("li", { class: "option-card" }, [
    el("div", { class: "option-text", text: `${o.role_id}: ${o.text}` }),
    el("div", { class: "option-meta", text: `${o.mapping_type}${o.trait_id ? ` → ${o.trait_label}(weight=${o.weight})` : ""}` }),
  ])));

  container.appendChild(el("div", { class: "question-card" }, [
    el("div", { class: "meta", text: `Blueprint ID: ${probe.blueprint_id}` }),
    el("div", { class: "question-text", text: probe.question_text }),
    traitPanel,
    optionList,
  ]));

  const visibleRows = sharedProbeVisibleContextRows(probe);
  if (visibleRows.length === 0) {
    container.appendChild(el("p", {}, "현재 배치·상태 필터에 해당하는 Context가 없습니다(필터를 확인하세요)."));
    return;
  }
  visibleRows.forEach((row) => container.appendChild(renderSharedProbeContextRow(probe, row)));
}

async function saveSharedProbeContextReview(blueprintId, contextId, payload, ui) {
  const button = ui && ui.button;
  const msg = ui && ui.msg;
  if (button) button.disabled = true;
  if (msg) {
    msg.textContent = "";
    msg.className = "inline-msg";
  }
  try {
    await apiPatch(`${API_BASE}/context-packs/shared-probes/${blueprintId}/${contextId}`, payload);
    setSaveIndicator("저장됨", "saved");
    if (msg) {
      msg.textContent = "저장됨";
      msg.className = "inline-msg ok";
    }
    state.dirty = false;
    await loadSharedProbesAll();
  } catch (err) {
    // §12/§14 — 422/409/그 외를 구분해서 보여주고, 실패했을 때 목록을 다시 불러와
    // 화면을 성공한 것처럼 되돌리지 않는다(현재 입력값을 그대로 유지한다).
    const text = err.status === 422 ? `입력 오류(422): ${err.message}`
      : err.status === 409 ? `충돌(409): ${err.message}`
      : `저장 실패${err.status ? `(${err.status})` : ""}: ${err.message}`;
    setSaveIndicator(text, "error");
    if (msg) {
      msg.textContent = text;
      msg.className = "inline-msg err";
    }
  } finally {
    if (button) button.disabled = false;
  }
}

/* ---- 2026-08-24 신규 ContextPack(business/science/sports 등 12개) 검수 탭 ----
 *
 * GET /internal/review/v2/context-packs 응답을 그대로 렌더링한다 — Pack 목록·질문
 * 구성·Trait Mapping을 이 파일에서 별도 상수로 복제하지 않는다(지시서 §3). 배치
 * 그룹(1차/2차/3차)도 서버가 계산해 내려주는 activation_batch를 그대로 쓴다 — 프론트에
 * 배치 표를 따로 두면 나중에 서버 정본과 어긋날 수 있어서다. 이 탭은 어떤 항목도
 * 스스로 APPROVE하지 않는다 — 사람이 저장 버튼을 눌렀을 때만, 그 사람이 실제로 고른
 * 값 그대로 PATCH한다. */

function contextPacksInBatch(batchNo) {
  return state.contextPacks
    .filter((p) => p.activation_batch === batchNo)
    .sort((a, b) => a.context_id.localeCompare(b.context_id));
}

function currentContextPack() {
  return state.contextPacks.find((p) => p.context_id === state.contextPackContextId) || null;
}

function contextPackReviewerStatusCounts(pack) {
  const counts = { APPROVE: 0, REVISE: 0, HOLD: 0, TBD: 0 };
  for (const q of pack.questions) {
    const status = q.review.reviewer_1_status;
    if (status in counts) counts[status] += 1;
  }
  return counts;
}

function orderedContextPackQuestions(pack) {
  // Array.prototype.sort는 안정 정렬이라(ES2019+) 같은 kind 안에서는 서버가 준
  // 원래 순서(예: seed 5개의 Anchor 순서)가 그대로 유지된다.
  return [...pack.questions].sort((a, b) => CONTEXTPACK_KIND_ORDER[a.kind] - CONTEXTPACK_KIND_ORDER[b.kind]);
}

function filteredContextPackQuestions(pack) {
  const ordered = orderedContextPackQuestions(pack);
  if (state.contextPackStatusFilter === "all") return ordered;
  return ordered.filter((q) => q.review.reviewer_1_status === state.contextPackStatusFilter);
}

async function loadContextPacksAll() {
  setSaveIndicator("신규 ContextPack 불러오는 중…", "");
  const resp = await apiGet(`${API_BASE}/context-packs`);
  state.contextPacks = resp.packs;
  state.contextPackDiscoveryErrors = resp.discovery_errors;
  state.contextPackOntologyErrors = resp.ontology_errors;
  if (state.contextPackContextId == null || !state.contextPacks.some((p) => p.context_id === state.contextPackContextId)) {
    // 기본 선택(지시서 §4): 1차 배치 → business. business 자체가 없으면(발견 실패 등)
    // 1차 배치의 다른 Context로, 그것도 없으면 전체 목록의 첫 Pack으로 물러난다.
    const batch1 = contextPacksInBatch(1);
    const fallback = batch1.find((p) => p.context_id === "business") || batch1[0] || state.contextPacks[0] || null;
    if (fallback) {
      state.contextPackBatch = fallback.activation_batch || 1;
      state.contextPackContextId = fallback.context_id;
    }
  }
  renderContextPackAll();
  setSaveIndicator("불러옴", "saved");
}

async function refreshContextPacksAfterSave(contextId, key) {
  const resp = await apiGet(`${API_BASE}/context-packs`);
  state.contextPacks = resp.packs;
  state.contextPackDiscoveryErrors = resp.discovery_errors;
  state.contextPackOntologyErrors = resp.ontology_errors;
  state.contextPackContextId = contextId;
  const pack = currentContextPack();
  if (pack) {
    const idx = orderedContextPackQuestions(pack).findIndex((q) => q.key === key);
    if (idx !== -1) state.contextPackQuestionIndex = idx;
  }
  renderContextPackAll();
}

function selectContextPackBatch(batchNo) {
  if (!confirmDiscardIfDirty()) return;
  state.contextPackBatch = batchNo;
  const contexts = contextPacksInBatch(batchNo);
  if (contexts.length > 0 && !contexts.some((p) => p.context_id === state.contextPackContextId)) {
    state.contextPackContextId = contexts[0].context_id;
    state.contextPackQuestionIndex = 0;
  }
  renderContextPackAll();
}

function selectContextPackContext(contextId) {
  if (!confirmDiscardIfDirty()) return;
  state.contextPackContextId = contextId;
  state.contextPackQuestionIndex = 0;
  renderContextPackAll();
}

function goToContextPackQuestionIndex(orderedIndex) {
  if (!confirmDiscardIfDirty()) return;
  state.contextPackQuestionIndex = orderedIndex;
  renderContextPackQuestionNavList();
  renderCurrentContextPackQuestion();
}

function stepContextPackQuestion(delta) {
  const pack = currentContextPack();
  if (!pack) return;
  const ordered = orderedContextPackQuestions(pack);
  const visible = filteredContextPackQuestions(pack);
  if (visible.length === 0) return;
  const currentQ = ordered[state.contextPackQuestionIndex];
  let pos = visible.indexOf(currentQ);
  if (pos === -1) pos = 0;
  const nextPos = Math.min(Math.max(pos + delta, 0), visible.length - 1);
  goToContextPackQuestionIndex(ordered.indexOf(visible[nextPos]));
}

function stepContextPackContext(delta) {
  const contexts = contextPacksInBatch(state.contextPackBatch);
  if (contexts.length === 0) return;
  const pos = contexts.findIndex((p) => p.context_id === state.contextPackContextId);
  const nextPos = Math.min(Math.max((pos === -1 ? 0 : pos) + delta, 0), contexts.length - 1);
  selectContextPackContext(contexts[nextPos].context_id);
}

function renderContextPackErrorBanner() {
  const box = document.getElementById("context-pack-error-banner");
  box.replaceChildren();
  const de = state.contextPackDiscoveryErrors || {};
  const oe = state.contextPackOntologyErrors || {};
  const deKeys = Object.keys(de);
  const oeKeys = Object.keys(oe);
  if (deKeys.length === 0 && oeKeys.length === 0) {
    box.className = "tab-only-context_packs";
    return;
  }
  box.className = "tab-only-context_packs context-pack-error-banner";
  if (deKeys.length > 0) {
    box.appendChild(el("div", {}, [
      el("strong", { text: "⚠ discovery_errors — 아래 Pack은 코드 오류로 발견 자체가 실패했다(목록에 없다 — 정상 Pack처럼 검수하지 마세요):" }),
    ]));
    deKeys.forEach((k) => box.appendChild(el("div", {}, `${k}: ${de[k]}`)));
  }
  if (oeKeys.length > 0) {
    box.appendChild(el("div", {}, [
      el("strong", { text: "⚠ ontology_errors — 아래 Pack은 Trait/Context 정본과 맞지 않아 제외됐다:" }),
    ]));
    oeKeys.forEach((k) => box.appendChild(el("div", {}, `${k}: ${oe[k]}`)));
  }
}

function renderContextPackBatchSelector() {
  const box = document.getElementById("context-pack-batch-selector");
  box.replaceChildren();
  const batchNumbers = [...new Set(state.contextPacks.map((p) => p.activation_batch).filter((b) => b != null))].sort((a, b) => a - b);
  batchNumbers.forEach((n) => {
    box.appendChild(
      el("button", {
        type: "button", class: n === state.contextPackBatch ? "active" : "",
        onclick: () => selectContextPackBatch(n),
      }, CONTEXTPACK_BATCH_LABEL[n] || `배치 ${n}`),
    );
  });
}

function renderContextPackBatchSummary() {
  const box = document.getElementById("context-pack-batch-summary");
  box.replaceChildren();
  const contexts = contextPacksInBatch(state.contextPackBatch);
  const statusTotals = { APPROVE: 0, REVISE: 0, HOLD: 0, TBD: 0 };
  let total = 0;
  const contextRows = contexts.map((p) => {
    const counts = contextPackReviewerStatusCounts(p);
    total += p.questions.length;
    for (const k of Object.keys(statusTotals)) statusTotals[k] += counts[k];
    return el("div", { class: "context-row" }, `${p.context_id}: ${counts.APPROVE} / ${p.questions.length}`);
  });
  box.appendChild(
    el("div", { class: "row" }, [
      el("strong", { text: CONTEXTPACK_BATCH_LABEL[state.contextPackBatch] || `배치 ${state.contextPackBatch}` }),
      el("span", { class: "n" }, `${statusTotals.APPROVE} / ${total} 승인`),
    ]),
  );
  contextRows.forEach((row) => box.appendChild(row));
  box.appendChild(el("hr"));
  ["APPROVE", "REVISE", "HOLD", "TBD"].forEach((k) => {
    box.appendChild(el("div", { class: "row" }, [el("span", { text: k }), el("span", { class: "n", text: String(statusTotals[k]) })]));
  });
}

function renderContextPackContextList() {
  const list = document.getElementById("context-pack-context-list");
  list.replaceChildren();
  contextPacksInBatch(state.contextPackBatch).forEach((p) => {
    const counts = contextPackReviewerStatusCounts(p);
    const item = el(
      "li",
      { class: p.context_id === state.contextPackContextId ? "current" : "", onclick: () => selectContextPackContext(p.context_id) },
      [el("span", { text: `${p.label} (${p.context_id})` }), el("span", { class: "n", text: `${counts.APPROVE}/${p.questions.length}` })],
    );
    list.appendChild(item);
  });
}

function renderContextPackQuestionNavList() {
  const list = document.getElementById("context-pack-question-nav-list");
  list.replaceChildren();
  const pack = currentContextPack();
  if (!pack) return;
  const ordered = orderedContextPackQuestions(pack);
  const visible = new Set(filteredContextPackQuestions(pack));
  ordered.forEach((q, idx) => {
    if (!visible.has(q)) return;
    const label = `${CONTEXTPACK_KIND_LABEL[q.kind]}${q.anchor_id ? " · " + q.anchor_id : ""}`;
    const item = el(
      "li",
      { class: idx === state.contextPackQuestionIndex ? "current" : "", onclick: () => goToContextPackQuestionIndex(idx) },
      [el("span", { text: label }), statusPill(q.review.reviewer_1_status)],
    );
    list.appendChild(item);
  });
}

function renderContextPackDetailHeader() {
  const box = document.getElementById("context-pack-detail-header");
  box.replaceChildren();
  const pack = currentContextPack();
  if (!pack) {
    box.appendChild(el("p", {}, "이 배치에 표시할 Context가 없습니다."));
    return;
  }
  box.appendChild(el("h2", { text: `${pack.label} (${pack.context_id})` }));
  box.appendChild(el("div", { class: "desc", text: pack.description }));
  box.appendChild(
    el("div", { class: "meta-row" }, `pack_version: ${pack.pack_version} · is_active(Runtime 서빙 중): ${pack.is_active ? "예" : "아니오"}`),
  );
  if (pack.registry_errors.length > 0) {
    box.appendChild(el("div", { class: "meta-row registry-error" }, `registry_errors: ${pack.registry_errors.join(", ")}`));
  }
  if (pack.forbidden_assumptions.length > 0) {
    box.appendChild(el("div", { class: "meta-row" }, `금지 전제: ${pack.forbidden_assumptions.join(" / ")}`));
  }
  box.appendChild(el("div", { class: "meta-row" }, "검수 상태 파일(읽기 전용 경로 표시):"));
  pack.review_artifact_paths.forEach((p) => box.appendChild(el("span", { class: "artifact-path", text: p })));
  box.appendChild(
    el(
      "div",
      { class: "meta-row" },
      `Trait Coverage: PRIMARY ${pack.coverage.primary_trait_ids.length}개 · 미포함 ${pack.coverage.uncovered_trait_ids.length}개 · Anchor ${pack.coverage.anchor_count}개 · Seed ${pack.coverage.seed_question_count}개 · Backup ${pack.coverage.backup_question_count}개`,
    ),
  );
}

function renderContextPackContextPager() {
  const contexts = contextPacksInBatch(state.contextPackBatch);
  const pos = contexts.findIndex((p) => p.context_id === state.contextPackContextId);
  document.getElementById("context-pack-context-pager-label").textContent = contexts.length
    ? `${pos + 1} / ${contexts.length} (${CONTEXTPACK_BATCH_LABEL[state.contextPackBatch] || state.contextPackBatch})`
    : "Context 없음";
  document.getElementById("context-pack-prev-context-btn").disabled = pos <= 0;
  document.getElementById("context-pack-next-context-btn").disabled = pos === -1 || pos >= contexts.length - 1;
}

function renderContextPackOptionCard(option) {
  const classes = ["option-card"];
  if (option.mapping_type === "NO_SIGNAL") classes.push("context-pack-nosignal");
  const metaSpans = [el("span", { text: `role_id: ${option.role_id}` }), el("span", { text: option.mapping_type })];
  if (option.mapping_type === "TRAIT_SIGNAL") {
    metaSpans.push(el("span", { text: `Trait: ${option.trait_label} (${option.trait_id})` }));
  }
  const details = [el("div", { class: "option-meta" }, metaSpans)];
  if (option.trait_definition) details.push(el("div", { class: "def", text: option.trait_definition }));
  if (option.mapping_rationale_draft) {
    details.push(
      el("div", { class: "mapping-rationale-draft", text: `Mapping Rationale Draft(팀 초안, 검증 완료 아님): ${option.mapping_rationale_draft}` }),
    );
  }
  return el("li", { class: classes.join(" ") }, [el("div", { class: "option-text", text: option.text }), ...details]);
}

function renderContextPackReviewPanel(pack, question) {
  const review = question.review;
  const editable = state.reviewerSlot === "reviewer_1";
  const finalBadge = el("span", { class: `final-status-badge status-pill ${review.final_status}`, text: review.final_status });

  if (!editable) {
    return el("div", { class: "review-panel" }, [
      el("div", {}, [el("strong", { text: "검토자 1 상태 " }), statusPill(review.reviewer_1_status), finalBadge]),
      el("p", { class: "inline-msg", text: review.reviewer_1_comment || "(의견 없음)" }),
      review.resolution_note ? el("p", { class: "inline-msg", text: `해소 메모: ${review.resolution_note}` }) : null,
      el("p", { class: "inline-msg", text: '저장하려면 상단에서 "검토자 1"을 선택하세요.' }),
    ]);
  }

  const statusValue = { current: review.reviewer_1_status };
  const radioGroup = el("div", { class: "status-radio-group" });
  ["TBD", "APPROVE", "REVISE", "HOLD"].forEach((value) => {
    const input = el("input", {
      type: "radio", name: `contextpack-${question.key}-status`, value,
      onchange: () => { statusValue.current = value; markDirty(); },
    });
    if (review.reviewer_1_status === value) input.setAttribute("checked", "checked");
    radioGroup.appendChild(el("label", {}, [input, document.createTextNode(value)]));
  });

  const commentBox = el("textarea", { class: "comment-box", placeholder: "검토 의견을 입력하세요", oninput: markDirty });
  commentBox.value = review.reviewer_1_comment || "";

  const resolutionBox = el("textarea", { class: "resolution-note-box", placeholder: "해소 메모(REVISE/HOLD 반영 경위 등)", oninput: markDirty });
  resolutionBox.value = review.resolution_note || "";

  const checklistItems = question.kind === "routing" ? CHECKLIST_CONTEXTPACK_ROUTING : CHECKLIST_CONTEXTPACK_SEED_BACKUP;
  const checklist = el(
    "div", { class: "checklist" },
    checklistItems.map((text, i) => el("label", {}, [el("input", { type: "checkbox", "data-checklist-index": String(i) }), document.createTextNode(text)])),
  );

  const msg = el("span", { class: "inline-msg" });
  const saveBtn = el("button", { class: "save-btn", type: "button" }, "저장");
  saveBtn.addEventListener("click", async () => {
    saveBtn.disabled = true;
    msg.textContent = "";
    msg.className = "inline-msg";
    try {
      const path = `${API_BASE}/context-packs/${encodeURIComponent(pack.context_id)}/${encodeURIComponent(question.key)}`;
      await apiPatch(path, { status: statusValue.current, comment: commentBox.value, resolution_note: resolutionBox.value });
      msg.textContent = "저장됨";
      msg.className = "inline-msg ok";
      state.dirty = false;
      await refreshContextPacksAfterSave(pack.context_id, question.key);
    } catch (err) {
      if (err.status === 422) msg.textContent = `입력 오류(422): ${err.message}`;
      else if (err.status === 409) msg.textContent = `충돌(409): ${err.message}`;
      else msg.textContent = `저장 실패${err.status ? `(${err.status})` : ""}: ${err.message}`;
      msg.className = "inline-msg err";
      // 실패했으므로 여기서 절대 refreshContextPacksAfterSave/state.dirty=false를
      // 부르지 않는다 — 화면은 사용자가 입력한 값을 그대로 유지한다(성공한 것처럼
      // 되돌리거나 지우지 않는다).
    } finally {
      saveBtn.disabled = false;
    }
  });

  return el("div", { class: "review-panel" }, [
    el("div", {}, [el("strong", { text: "검토자 1 상태 " }), finalBadge]),
    radioGroup,
    commentBox,
    el("div", {}, [el("strong", { text: "해소 메모" })]),
    resolutionBox,
    checklist,
    el("div", { class: "save-row" }, [saveBtn, msg]),
  ]);
}

function renderCurrentContextPackQuestion() {
  const container = document.getElementById("context-pack-question-container");
  container.replaceChildren();
  const pack = currentContextPack();
  if (!pack) {
    container.appendChild(el("p", {}, "이 배치에 표시할 Context가 없습니다."));
    document.getElementById("pager-label").textContent = "";
    document.getElementById("prev-btn").disabled = true;
    document.getElementById("next-btn").disabled = true;
    return;
  }
  const ordered = orderedContextPackQuestions(pack);
  const question = ordered[state.contextPackQuestionIndex];
  if (!question) {
    container.appendChild(el("p", {}, "표시할 질문이 없습니다(상태 필터를 확인하세요)."));
    document.getElementById("pager-label").textContent = "필터 결과 없음";
    document.getElementById("prev-btn").disabled = true;
    document.getElementById("next-btn").disabled = true;
    return;
  }

  const meta = el("div", { class: "meta" }, [
    el("span", { text: `kind: ${CONTEXTPACK_KIND_LABEL[question.kind]} · key: ${question.key}` }),
    question.anchor_id ? el("span", { text: ` · anchor_id: ${question.anchor_id}` }) : null,
  ]);

  const signalBanner = question.trait_signal_free
    ? el("div", { class: "trait-signal-free-banner", text: "✓ Trait Signal 없음(구조적으로 보장됨) — 이 질문의 답변은 어떤 Trait 점수에도 반영되지 않는다" })
    : el("div", { class: "trait-signal-present-warning", text: "⚠ Trait Signal 존재 — 아래 선택지별 Mapping을 확인하세요" });

  const optionList = el("ul", { class: "option-list" }, question.options.map((o) => renderContextPackOptionCard(o)));
  const reviewPanel = renderContextPackReviewPanel(pack, question);

  container.appendChild(
    el("div", { class: "question-card" }, [meta, el("div", { class: "question-text", text: question.question_text }), signalBanner, optionList, reviewPanel]),
  );

  const visible = filteredContextPackQuestions(pack);
  const pos = visible.indexOf(question);
  document.getElementById("pager-label").textContent = visible.length
    ? `${pos + 1} / ${visible.length} (전체 ${ordered.length}개 중)`
    : "필터 결과 없음";
  document.getElementById("prev-btn").disabled = pos <= 0;
  document.getElementById("next-btn").disabled = pos === -1 || pos >= visible.length - 1;
}

function renderContextPackAll() {
  renderContextPackErrorBanner();
  renderContextPackBatchSelector();
  renderContextPackBatchSummary();
  renderContextPackContextList();
  renderContextPackQuestionNavList();
  renderContextPackDetailHeader();
  renderCurrentContextPackQuestion();
  renderContextPackContextPager();
}

/* 2026-08-24 지시서(a/canonical-major-bridge-review-ui) — Canonical Major Group
 * Bridge(44행) 검수 탭. 다른 탭과 달리 "질문 하나 = Pager 한 칸" 모델이 아니라
 * 필터링된 행 전체를 카드 목록으로 한 화면에 그린다(44행은 Pager 없이도 다룰 만한
 * 크기). PATCH는 각 카드의 "저장" 버튼을 눌렀을 때만 전송되고, 필터 변경 핸들러는
 * renderBridgeContainer()만 다시 호출한다 — apiPatch를 호출하는 코드 경로가 저장
 * 버튼 클릭 핸들러 하나뿐이라는 사실 자체가 "필터가 저장을 유발하지 않는다"는
 * 증거다. */

const BRIDGE_REPRESENTATIVE_MAJOR_IDS = ["media_communication", "industrial_engineering", "hci_ux"];

async function loadBridgeAll() {
  const resp = await apiGet(`${API_BASE}/canonical-major-group-bridge`);
  state.bridgeRows = resp.rows;
  state.bridgeSummary = resp.summary;
  renderBridgeAll();
}

function renderBridgeSummary() {
  const s = state.bridgeSummary;
  const box = document.getElementById("bridge-summary-box");
  if (!s) {
    box.textContent = "불러오는 중…";
    return;
  }
  box.replaceChildren(
    el("div", { class: "row" }, [el("span", {}, "전체"), el("span", { class: "n" }, String(s.total))]),
    el("div", { class: "row" }, [el("span", {}, "EVIDENCED"), el("span", { class: "n" }, String(s.evidenced_count))]),
    el("div", { class: "row" }, [
      el("span", {}, "REVIEW_REQUIRED"), el("span", { class: "n" }, String(s.review_required_count)),
    ]),
    el("div", { class: "row" }, [
      el("span", {}, "EXCLUDED_RECOMMENDATION"), el("span", { class: "n" }, String(s.excluded_recommendation_count)),
    ]),
    el("div", { class: "row" }, [el("span", {}, "UNMAPPED"), el("span", { class: "n" }, String(s.unmapped_count))]),
    el("hr"),
    el("div", { class: "row" }, [el("span", {}, "검토자 상태 TBD"), el("span", { class: "n" }, String(s.reviewer_tbd_count))]),
    el("div", { class: "row" }, [
      el("span", {}, "검토자 상태 APPROVE"), el("span", { class: "n" }, String(s.reviewer_approve_count)),
    ]),
    el("div", { class: "row" }, [
      el("span", {}, "검토자 상태 REVISE"), el("span", { class: "n" }, String(s.reviewer_revise_count)),
    ]),
    el("div", { class: "row" }, [el("span", {}, "검토자 상태 HOLD"), el("span", { class: "n" }, String(s.reviewer_hold_count))]),
    el("hr"),
    el("div", { class: "row" }, [el("span", {}, "검수 완료"), el("span", { class: "n" }, String(s.reviewed_count))]),
    el("div", { class: "row" }, [el("span", {}, "미검수"), el("span", { class: "n" }, String(s.unreviewed_count))]),
  );
}

function bridgeRowMatchesFilters(row) {
  const f = state.bridgeFilters;
  if (f.mapping !== "all" && row.mapping_status !== f.mapping) return false;
  if (f.reviewStatus === "unreviewed" && row.review.reviewer_1_status !== "TBD") return false;
  if (f.reviewStatus === "reviewed" && row.review.reviewer_1_status === "TBD") return false;
  if (f.boundary && !row.is_boundary_case) return false;
  if (f.major !== "all") {
    if (f.major === "other") {
      if (row.canonical_major_id && BRIDGE_REPRESENTATIVE_MAJOR_IDS.includes(row.canonical_major_id)) return false;
    } else if (row.canonical_major_id !== f.major) {
      return false;
    }
  }
  return true;
}

function filteredBridgeRows() {
  return state.bridgeRows.filter(bridgeRowMatchesFilters);
}

function renderBridgeRowCard(row) {
  const card = el("div", { class: `bridge-row-card${row.is_boundary_case ? " is-boundary" : ""}` });
  card.appendChild(el("h3", {}, `${row.canonical_major_group_label} (${row.canonical_major_group_id})`));
  card.appendChild(
    el(
      "div", { class: "meta-row" },
      `연결 후보 서비스 전공: ${row.canonical_major_label ? `${row.canonical_major_label} (${row.canonical_major_id})` : "없음 (UNMAPPED)"}`,
    ),
  );
  card.appendChild(
    el("div", { class: "meta-row" }, [
      statusPill(row.mapping_status),
      ` · 전국 학과 후보 ${row.national_department_candidate_count == null ? "알 수 없음" : `${row.national_department_candidate_count}개`}`,
    ]),
  );

  if (row.evidence.length > 0) {
    const list = el("ul", { class: "evidence-list" });
    for (const item of row.evidence) list.appendChild(el("li", {}, item));
    card.appendChild(list);
  }
  card.appendChild(el("div", { class: "decision-reason" }, `판단 근거: ${row.decision_reason || "(없음)"}`));
  if (row.boundary_notes) {
    card.appendChild(el("div", { class: "boundary-notes" }, `경계 사례 메모: ${row.boundary_notes}`));
  }

  const statusSelect = el("select", {});
  for (const value of ["TBD", "APPROVE", "REVISE", "HOLD"]) {
    const opt = el("option", { value }, value);
    if (value === row.review.reviewer_1_status) opt.selected = true;
    statusSelect.appendChild(opt);
  }

  const commentBox = el("textarea", { class: "bridge-comment-box", placeholder: "검토자 코멘트" });
  commentBox.value = row.review.reviewer_1_comment;

  const msg = el("span", { class: "inline-msg" });
  const saveBtn = el("button", { class: "save-btn", type: "button", text: "저장" });
  saveBtn.addEventListener("click", async () => {
    // 안전 규칙 "저장 버튼을 눌렀을 때만 상태·코멘트 저장" — apiPatch 호출은 이
    // 클릭 핸들러 안에만 있다. 필터 변경 핸들러는 이 함수를 호출하지 않는다.
    saveBtn.disabled = true;
    msg.textContent = "";
    msg.className = "inline-msg";
    try {
      await apiPatch(`${API_BASE}/canonical-major-group-bridge/${encodeURIComponent(row.review_key)}`, {
        status: statusSelect.value, comment: commentBox.value, resolution_note: null,
      });
      await loadBridgeAll();
    } catch (err) {
      msg.textContent = `저장 실패: ${err.message}`;
      msg.className = "inline-msg err";
    } finally {
      saveBtn.disabled = false;
    }
  });

  const controls = el("div", { class: "review-controls" }, [statusPill(row.review.final_status), statusSelect, saveBtn, msg]);
  card.appendChild(controls);
  card.appendChild(commentBox);
  return card;
}

function renderBridgeContainer() {
  const container = document.getElementById("bridge-container");
  const rows = filteredBridgeRows();
  if (rows.length === 0) {
    container.replaceChildren(el("div", { class: "bridge-empty-msg" }, "조건에 맞는 행이 없습니다."));
    return;
  }
  const list = el("div", { class: "bridge-row-list" });
  for (const row of rows) list.appendChild(renderBridgeRowCard(row));
  container.replaceChildren(list);
}

function renderBridgeAll() {
  renderBridgeSummary();
  renderBridgeContainer();
}

/* ---- Hash Deep Link(#context-packs, #shared-probes?batch=1 등) — 탭마다 안정적인
 * hash를 매핑해, 새로고침해도 같은 탭이 유지되게 한다. shared_probes 탭은 배치까지
 * "?batch=N" 쿼리로 남긴다(예: #shared-probes?batch=1). 이 프로젝트는 localStorage로
 * 탭을 기억하지 않으므로(grep 결과 review.js 전체에 localStorage 사용 없음) hash와
 * 충돌할 기존 저장값이 없다 — hash가 항상 유일한 진실이다. */

const CONTEXTPACK_TAB_HASH = {
  direct_probe: "direct-probe", routing: "routing", seed_anchor: "seed-anchor",
  backup: "backup", anchor_backup: "anchor-backup", shared_probes: "shared-probes",
  context_packs: "context-packs", bridge: "bridge",
};
const CONTEXTPACK_HASH_TO_TAB = Object.fromEntries(Object.entries(CONTEXTPACK_TAB_HASH).map(([tab, hash]) => [hash, tab]));

/* {tab, batch}를 반환한다. tab이 null이면 "알 수 없는 hash"(안전한 기본 탭으로
 * 복귀해야 함), batch가 null이면 "hash에 batch가 없거나 1/2/3이 아닌 값"(1차로
 * 안전하게 복귀해야 함, §4). */
function parseLocationHash() {
  const raw = (location.hash || "").replace(/^#/, "");
  const [hashPart, queryPart] = raw.split("?");
  const tab = CONTEXTPACK_HASH_TO_TAB[hashPart] || null;
  let batch = null;
  if (queryPart) {
    const params = new URLSearchParams(queryPart);
    const parsed = parseInt(params.get("batch"), 10);
    batch = [1, 2, 3].includes(parsed) ? parsed : null;
  }
  return { tab, batch };
}

function tabFromLocationHash() {
  return parseLocationHash().tab;
}

function currentHashString() {
  let hash = CONTEXTPACK_TAB_HASH[state.tab];
  if (state.tab === "shared_probes") {
    hash += `?batch=${state.sharedProbeBatch === "all" ? "all" : state.sharedProbeBatch}`;
  }
  return "#" + hash;
}

let _suppressHashSync = false;
function syncHash() {
  const target = currentHashString();
  if (location.hash === target) return;
  _suppressHashSync = true;
  location.hash = target.slice(1);
  setTimeout(() => { _suppressHashSync = false; }, 0);
}

window.addEventListener("hashchange", () => {
  if (_suppressHashSync) return;
  const { tab, batch } = parseLocationHash();
  const targetTab = tab || "direct_probe";
  if (targetTab === "shared_probes" && state.tab === "shared_probes") {
    // 이미 이 탭에 있으면 setTab()의 "같은 탭이면 무시" 가드에 걸려 배치가 반영되지
    // 않는다 — 배치만 바꾸는 경로를 따로 둔다(예: #shared-probes?batch=1 →
    // #shared-probes?batch=2로 주소창에서 직접 바꾼 경우).
    selectSharedProbeBatch(batch || 1, { skipHashSync: true });
    return;
  }
  if (targetTab === "shared_probes") state.sharedProbeBatch = batch || 1;
  setTab(targetTab);
});

function applyTabClasses(tab) {
  document.body.classList.toggle("tab-direct_probe", tab === "direct_probe");
  document.body.classList.toggle("tab-routing", tab === "routing");
  document.body.classList.toggle("tab-seed_anchor", tab === "seed_anchor");
  document.body.classList.toggle("tab-backup", tab === "backup");
  document.body.classList.toggle("tab-anchor_backup", tab === "anchor_backup");
  document.body.classList.toggle("tab-shared_probes", tab === "shared_probes");
  document.body.classList.toggle("tab-context_packs", tab === "context_packs");
  document.body.classList.toggle("tab-bridge", tab === "bridge");
  document.getElementById("tab-direct-probe-btn").classList.toggle("active", tab === "direct_probe");
  document.getElementById("tab-routing-btn").classList.toggle("active", tab === "routing");
  document.getElementById("tab-seed-anchor-btn").classList.toggle("active", tab === "seed_anchor");
  document.getElementById("tab-backup-btn").classList.toggle("active", tab === "backup");
  document.getElementById("tab-anchor-backup-btn").classList.toggle("active", tab === "anchor_backup");
  document.getElementById("tab-shared-probes-btn").classList.toggle("active", tab === "shared_probes");
  document.getElementById("tab-context-packs-btn").classList.toggle("active", tab === "context_packs");
  document.getElementById("tab-bridge-btn").classList.toggle("active", tab === "bridge");
  // 공용 Adaptive Probe 탭과 마찬가지로 "질문 하나 = Pager 한 칸" 모델이 아닌 탭만
  // 여기서 pager-bar를 숨긴다 — 신규 ContextPack 탭은 이 모델을 그대로 쓰므로
  // (Context 안에서 이전/다음 질문) 계속 보여준다. Bridge 탭도 44행 카드 목록
  // 모델이라 Pager가 필요 없다.
  document.getElementById("pager-bar").style.display = tab === "shared_probes" || tab === "bridge" ? "none" : "flex";
}

async function loadOrRenderTab(tab) {
  if (tab === "shared_probes") {
    if (state.sharedProbes.length === 0) {
      try {
        await loadSharedProbesAll();
      } catch (err) {
        setSaveIndicator(`공용 Adaptive Probe 불러오기 실패: ${err.message}`, "error");
      }
    } else {
      renderSharedProbeBatchSelector();
      renderSharedProbeProgressDashboard();
      renderSharedProbesSidebarList();
      renderCurrentSharedProbe();
    }
  } else if (tab === "routing") {
    if (state.routingQuestions.length === 0) {
      try {
        await loadRoutingAll();
      } catch (err) {
        setSaveIndicator(`Routing 불러오기 실패: ${err.message}`, "error");
      }
    } else {
      renderRoutingSidebarList();
      renderCurrentRoutingQuestion();
    }
  } else if (tab === "seed_anchor") {
    if (state.seedAnchorQuestions.length === 0) {
      try {
        await loadSeedAnchorAll();
      } catch (err) {
        setSaveIndicator(`Seed Anchor Variant 불러오기 실패: ${err.message}`, "error");
      }
    } else {
      renderSeedAnchorSidebarList();
      renderCurrentSeedAnchorQuestion();
    }
  } else if (tab === "backup") {
    if (state.backupQuestions.length === 0) {
      try {
        await loadBackupAll();
      } catch (err) {
        setSaveIndicator(`Backup Question 불러오기 실패: ${err.message}`, "error");
      }
    } else {
      renderBackupSidebarList();
      renderCurrentBackupQuestion();
    }
  } else if (tab === "anchor_backup") {
    if (state.anchorBackupQuestions.length === 0) {
      try {
        await loadAnchorBackupAll();
      } catch (err) {
        setSaveIndicator(`Anchor Backup 불러오기 실패: ${err.message}`, "error");
      }
    } else {
      renderAnchorBackupSidebarList();
      renderCurrentAnchorBackupQuestion();
    }
  } else if (tab === "context_packs") {
    if (state.contextPacks.length === 0) {
      try {
        await loadContextPacksAll();
      } catch (err) {
        setSaveIndicator(`신규 ContextPack 불러오기 실패: ${err.message}`, "error");
      }
    } else {
      renderContextPackAll();
    }
  } else if (tab === "bridge") {
    if (state.bridgeRows.length === 0) {
      try {
        await loadBridgeAll();
      } catch (err) {
        setSaveIndicator(`Canonical Major Group Bridge 불러오기 실패: ${err.message}`, "error");
      }
    } else {
      renderBridgeAll();
    }
  } else {
    if (state.questions.length === 0) {
      try {
        await loadAll();
      } catch (err) {
        setSaveIndicator(`불러오기 실패: ${err.message}`, "error");
      }
    } else {
      renderSidebarList();
      renderCurrentQuestion();
    }
  }
}

async function setTab(tab) {
  if (tab === state.tab) return;
  if (!confirmDiscardIfDirty()) return;
  state.tab = tab;
  syncHash();
  applyTabClasses(tab);
  await loadOrRenderTab(tab);
}

function setupControls() {
  document.getElementById("reviewer-select").addEventListener("change", (e) => {
    if (state.dirty) {
      const proceed = confirm("검토자를 바꾸면 저장하지 않은 변경사항이 사라집니다. 계속할까요?");
      if (!proceed) {
        e.target.value = state.reviewerSlot;
        return;
      }
    }
    state.reviewerSlot = e.target.value;
    state.dirty = false;
    const warning = document.getElementById("reviewer-warning");
    warning.textContent = state.reviewerSlot ? "" : "검토자를 선택해야 저장할 수 있습니다";
    // 신규 ContextPack 탭에 있는 동안 검토자를 고르면 그 자리에서 바로 편집 가능
    // 상태로 바뀌어야 한다(다른 탭을 오갈 필요 없이) — 이 탭만 별도 렌더 함수를 쓴다.
    if (state.tab === "context_packs") renderCurrentContextPackQuestion();
    else renderCurrentQuestion();
  });
  document.getElementById("reviewer-warning").textContent = "검토자를 선택해야 저장할 수 있습니다";

  document.getElementById("mode-student-btn").addEventListener("click", () => setMode("student"));
  document.getElementById("mode-mapping-btn").addEventListener("click", () => setMode("mapping"));

  document.getElementById("tab-direct-probe-btn").addEventListener("click", () => setTab("direct_probe"));
  document.getElementById("tab-routing-btn").addEventListener("click", () => setTab("routing"));
  document.getElementById("tab-seed-anchor-btn").addEventListener("click", () => setTab("seed_anchor"));
  document.getElementById("tab-backup-btn").addEventListener("click", () => setTab("backup"));
  document.getElementById("tab-anchor-backup-btn").addEventListener("click", () => setTab("anchor_backup"));
  document.getElementById("tab-shared-probes-btn").addEventListener("click", () => setTab("shared_probes"));
  document.getElementById("tab-context-packs-btn").addEventListener("click", () => setTab("context_packs"));
  document.getElementById("tab-bridge-btn").addEventListener("click", () => setTab("bridge"));

  document.getElementById("prev-btn").addEventListener("click", () => {
    if (state.tab === "shared_probes" || state.tab === "bridge") return; // 이 탭들은 Pager를 쓰지 않는다.
    if (state.tab === "routing") stepRoutingQuestion(-1);
    else if (state.tab === "seed_anchor") stepSeedAnchorQuestion(-1);
    else if (state.tab === "anchor_backup") stepAnchorBackupQuestion(-1);
    else if (state.tab === "backup") stepBackupQuestion(-1);
    else if (state.tab === "context_packs") stepContextPackQuestion(-1);
    else stepQuestion(-1);
  });
  document.getElementById("next-btn").addEventListener("click", () => {
    if (state.tab === "shared_probes" || state.tab === "bridge") return;
    if (state.tab === "routing") stepRoutingQuestion(1);
    else if (state.tab === "seed_anchor") stepSeedAnchorQuestion(1);
    else if (state.tab === "anchor_backup") stepAnchorBackupQuestion(1);
    else if (state.tab === "backup") stepBackupQuestion(1);
    else if (state.tab === "context_packs") stepContextPackQuestion(1);
    else stepQuestion(1);
  });

  document.getElementById("context-pack-prev-context-btn").addEventListener("click", () => stepContextPackContext(-1));
  document.getElementById("context-pack-next-context-btn").addEventListener("click", () => stepContextPackContext(1));

  document.querySelectorAll('input[name="context-pack-status-filter"]').forEach((input) => {
    input.addEventListener("change", () => {
      state.contextPackStatusFilter = input.value;
      renderContextPackQuestionNavList();
      renderCurrentContextPackQuestion();
    });
  });

  document.querySelectorAll('input[name="shared-probe-status-filter"]').forEach((input) => {
    input.addEventListener("change", () => {
      state.sharedProbeStatusFilter = input.value;
      renderSharedProbesSidebarList();
      renderCurrentSharedProbe();
    });
  });

  document.querySelectorAll('input[name="status-filter"]').forEach((input) => {
    input.addEventListener("change", () => {
      state.filters.status = input.value;
      renderSidebarList();
      renderCurrentQuestion();
    });
  });
  document.getElementById("filter-question-flag").addEventListener("change", (e) => {
    state.filters.questionFlag = e.target.checked;
    renderSidebarList();
    renderCurrentQuestion();
  });
  document.getElementById("filter-option-flag").addEventListener("change", (e) => {
    state.filters.optionFlag = e.target.checked;
    renderSidebarList();
    renderCurrentQuestion();
  });
  document.getElementById("filter-no-signal").addEventListener("change", (e) => {
    state.filters.noSignal = e.target.checked;
    renderSidebarList();
    renderCurrentQuestion();
  });
  document.getElementById("filter-length-history").addEventListener("change", (e) => {
    state.filters.lengthHistory = e.target.checked;
    renderSidebarList();
    renderCurrentQuestion();
  });
  document.getElementById("filter-trait").addEventListener("change", (e) => {
    state.filters.trait = e.target.value;
    renderSidebarList();
    renderCurrentQuestion();
  });
  document.getElementById("filter-context").addEventListener("change", (e) => {
    state.filters.context = e.target.value;
    renderSidebarList();
    renderCurrentQuestion();
  });

  document.querySelectorAll('input[name="bridge-mapping-filter"]').forEach((input) => {
    input.addEventListener("change", () => {
      state.bridgeFilters.mapping = input.value;
      renderBridgeContainer();
    });
  });
  document.querySelectorAll('input[name="bridge-review-filter"]').forEach((input) => {
    input.addEventListener("change", () => {
      state.bridgeFilters.reviewStatus = input.value;
      renderBridgeContainer();
    });
  });
  document.getElementById("bridge-filter-boundary").addEventListener("change", (e) => {
    state.bridgeFilters.boundary = e.target.checked;
    renderBridgeContainer();
  });
  document.querySelectorAll('input[name="bridge-major-filter"]').forEach((input) => {
    input.addEventListener("change", () => {
      state.bridgeFilters.major = input.value;
      renderBridgeContainer();
    });
  });

  document.addEventListener("keydown", (e) => {
    const tag = (e.target && e.target.tagName) || "";
    if (tag === "TEXTAREA" || tag === "INPUT" || tag === "SELECT") return;
    if (state.tab === "shared_probes" || state.tab === "bridge") return; // 이 탭들은 화살표 키 이동을 쓰지 않는다.
    if (e.key === "ArrowLeft") {
      if (state.tab === "routing") stepRoutingQuestion(-1);
      else if (state.tab === "seed_anchor") stepSeedAnchorQuestion(-1);
      else if (state.tab === "anchor_backup") stepAnchorBackupQuestion(-1);
      else if (state.tab === "backup") stepBackupQuestion(-1);
      else if (state.tab === "context_packs") stepContextPackQuestion(-1);
      else stepQuestion(-1);
    }
    if (e.key === "ArrowRight") {
      if (state.tab === "routing") stepRoutingQuestion(1);
      else if (state.tab === "seed_anchor") stepSeedAnchorQuestion(1);
      else if (state.tab === "anchor_backup") stepAnchorBackupQuestion(1);
      else if (state.tab === "backup") stepBackupQuestion(1);
      else if (state.tab === "context_packs") stepContextPackQuestion(1);
      else stepQuestion(1);
    }
  });

  window.addEventListener("beforeunload", (e) => {
    if (state.dirty) {
      e.preventDefault();
      e.returnValue = "";
    }
  });
}

function setMode(mode) {
  state.mode = mode;
  document.body.classList.toggle("mode-student", mode === "student");
  document.body.classList.toggle("mode-mapping", mode === "mapping");
  document.getElementById("mode-student-btn").classList.toggle("active", mode === "student");
  document.getElementById("mode-mapping-btn").classList.toggle("active", mode === "mapping");
}

async function bootstrap() {
  setupControls();
  // Deep Link: hash가 있으면 그 탭으로 바로 연다(예: #context-packs,
  // #shared-probes?batch=1). hash가 없거나 알 수 없으면 기존 동작(direct_probe
  // 기본 탭, shared_probes면 1차 배치)을 그대로 보존한다.
  const { tab, batch } = parseLocationHash();
  const initialTab = tab || "direct_probe";
  state.tab = initialTab;
  if (initialTab === "shared_probes") state.sharedProbeBatch = batch || 1;
  applyTabClasses(initialTab);
  try {
    await loadOrRenderTab(initialTab);
  } catch (err) {
    setSaveIndicator(`불러오기 실패: ${err.message}`, "error");
  }
}

bootstrap();
