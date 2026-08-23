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
  currentIndex: 0,
  filters: { status: "all", questionFlag: false, optionFlag: false, noSignal: false, lengthHistory: false, trait: "", context: "" },
  dirty: false, // 저장하지 않은 변경사항 존재 여부(현재 열린 편집 영역 기준)
};

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
    el("div", { class: "row" }, [el("span", {}, "TEAM_REVIEWED 가능 질문 수"), el("span", { class: "n" }, `${s.team_reviewed_eligible_blueprint_ids.length}`)]),
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

function renderReviewerSlotBlock({ scope, blueprintId, roleId, review, onSaved }) {
  const isSlot1Editable = state.reviewerSlot === "reviewer_1";
  const isSlot2Editable = state.reviewerSlot === "reviewer_2";

  const block1 = renderSingleSlotBlock({
    slot: "reviewer_1", label: "검토자 1", editable: isSlot1Editable,
    status: review.reviewer_1_status, comment: review.reviewer_1_comment,
    scope, blueprintId, roleId, onSaved,
  });
  const block2 = renderSingleSlotBlock({
    slot: "reviewer_2", label: "검토자 2", editable: isSlot2Editable,
    status: review.reviewer_2_status, comment: review.reviewer_2_comment,
    scope, blueprintId, roleId, onSaved,
  });

  const finalBadge = el("span", { class: `final-status-badge status-pill ${review.final_status}`, text: review.final_status });

  return el("div", { class: "review-panel" }, [
    el("div", {}, [el("strong", {}, "검토 상태 "), finalBadge]),
    el("div", { class: "slot-columns" }, [block1, block2]),
  ]);
}

function renderSingleSlotBlock({ slot, label, editable, status, comment, scope, blueprintId, roleId, onSaved }) {
  const checklistItems = scope === "question" ? CHECKLIST_QUESTION : CHECKLIST_OPTION;

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
      const revisionKey = scope === "question" ? "questionRevision" : "optionRevision";
      const path = scope === "question"
        ? `${API_BASE}/questions/${encodeURIComponent(blueprintId)}`
        : `${API_BASE}/questions/${encodeURIComponent(blueprintId)}/options/${encodeURIComponent(roleId)}`;
      const result = await apiPatch(path, {
        reviewer: slot, status: statusValue.current, comment: commentBox.value,
        expected_revision: state[revisionKey],
      });
      state[revisionKey] = result.new_revision;
      msg.textContent = "저장됨";
      msg.className = "inline-msg ok";
      state.dirty = false;
      await refreshAfterSave();
      if (onSaved) onSaved();
    } catch (err) {
      if (err.status === 409) {
        msg.textContent = "충돌: 다른 곳에서 먼저 저장됨 — 새로고침이 필요합니다";
        msg.className = "inline-msg err";
        await reloadAfterConflict();
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
    renderCurrentQuestion();
  });
  document.getElementById("reviewer-warning").textContent = "검토자를 선택해야 저장할 수 있습니다";

  document.getElementById("mode-student-btn").addEventListener("click", () => setMode("student"));
  document.getElementById("mode-mapping-btn").addEventListener("click", () => setMode("mapping"));

  document.getElementById("prev-btn").addEventListener("click", () => stepQuestion(-1));
  document.getElementById("next-btn").addEventListener("click", () => stepQuestion(1));

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

  document.addEventListener("keydown", (e) => {
    const tag = (e.target && e.target.tagName) || "";
    if (tag === "TEXTAREA" || tag === "INPUT" || tag === "SELECT") return;
    if (e.key === "ArrowLeft") stepQuestion(-1);
    if (e.key === "ArrowRight") stepQuestion(1);
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
  try {
    await loadAll();
  } catch (err) {
    setSaveIndicator(`불러오기 실패: ${err.message}`, "error");
  }
}

bootstrap();
