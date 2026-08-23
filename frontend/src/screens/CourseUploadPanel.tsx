/**
 * 학교 편제표 업로드 → 파싱 결과 확인 → 개설과목 확정.
 *
 * 지켜야 할 것:
 * - PDF·XLSX만 허용(XLS는 명시적으로 거부), 10MB 상한. 서버가 막기 전에 화면에서도 안내한다.
 * - confidence(high/low/unmatched)는 서버 판정 그대로 쓴다. 화면에서 유사도를 다시 계산하지 않는다.
 * - "high"를 기본 선택으로 두는 건 괜찮지만, 확정은 반드시 사용자가 /course/confirm을 눌러야 한다.
 * - unmatched는 matched_subject_id가 없어 구조적으로 확정할 수 없다 — 선택 불가로 표시한다.
 */
import { useMemo, useState } from "react";
import { confirmCourseSelection, uploadCourseDocument } from "@/api/endpoints";
import type { CourseUploadResponse, ParsedSubjectCandidate } from "@/api/contracts";
import { ErrorView } from "@/components/ErrorView";
import { Badge, Button, Card, SectionTitle, Spinner, StateBlock } from "@/components/ui";
import { useAction } from "@/hooks/useAsync";
import { useAppState } from "@/session/AppState";

const MAX_BYTES = 10 * 1024 * 1024;

export function validateFile(file: File): string | null {
  const name = file.name.toLowerCase();
  if (name.endsWith(".xls")) {
    return "예전 엑셀 형식(.xls)은 읽을 수 없어요. 엑셀에서 XLSX로 다시 저장한 뒤 올려주세요.";
  }
  if (!name.endsWith(".pdf") && !name.endsWith(".xlsx")) {
    return "PDF 또는 XLSX 파일만 올릴 수 있어요.";
  }
  if (file.size === 0) return "빈 파일이에요. 내용이 있는 파일을 올려주세요.";
  if (file.size > MAX_BYTES) return "파일이 너무 커요. 10MB 이하로 올려주세요.";
  return null;
}

const CONFIDENCE_NOTE: Record<ParsedSubjectCandidate["confidence"], string> = {
  high: "이름이 정확히 맞았어요",
  low: "비슷한 과목을 찾았어요. 맞는지 확인해주세요",
  unmatched: "어떤 과목인지 찾지 못했어요",
};

export function CourseUploadPanel({ onConfirmed }: { onConfirmed: () => void }) {
  const { state, dispatch } = useAppState();
  const [fileError, setFileError] = useState<string | null>(null);
  const [uploaded, setUploaded] = useState<CourseUploadResponse | null>(null);
  const [checked, setChecked] = useState<Set<string>>(new Set());

  const upload = useAction(async (file: File) => {
    if (!state.sessionId || !state.selectedMajorId) return;
    const response = await uploadCourseDocument(state.sessionId, state.selectedMajorId, file);
    setUploaded(response);
    // high는 기본 선택으로 제안하되, 확정은 사용자가 누른 뒤에만 일어난다.
    setChecked(
      new Set(
        response.parsed_candidates
          .filter((c) => c.confidence === "high" && c.matched_subject_id !== null)
          .map((c) => c.matched_subject_id as string),
      ),
    );
    return response;
  });

  const confirm = useAction(async () => {
    if (!state.sessionId) return;
    await confirmCourseSelection(state.sessionId, [...checked]);
    dispatch({ type: "courses_confirmed" });
    onConfirmed();
  });

  const selectable = useMemo(
    () => (uploaded?.parsed_candidates ?? []).filter((c) => c.matched_subject_id !== null),
    [uploaded],
  );
  const unresolved = useMemo(
    () => (uploaded?.parsed_candidates ?? []).filter((c) => c.matched_subject_id === null),
    [uploaded],
  );

  function handleFile(file: File | undefined) {
    if (!file) return;
    const problem = validateFile(file);
    setFileError(problem);
    if (!problem) void upload.run(file);
  }

  return (
    <Card>
      <SectionTitle hint="우리 학교가 실제로 여는 과목을 알려주면, 들을 수 있는 과목만 골라서 다시 추천할게요.">
        학교 편제표 올리기
      </SectionTitle>

      <label className="block cursor-pointer rounded-[20px] border-2 border-dashed px-5 py-9 text-center transition-colors"
        style={{ borderColor: "var(--color-neutral-300)" }}>
        <input
          type="file"
          accept=".pdf,.xlsx,application/pdf,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
          className="sr-only"
          onChange={(event) => handleFile(event.target.files?.[0])}
          disabled={upload.pending}
        />
        {upload.pending ? (
          <Spinner label="문서를 읽는 중" />
        ) : (
          <>
            <p className="text-[16px] font-semibold" style={{ fontFamily: "var(--font-heading)" }}>파일 선택하기</p>
            <p className="mut mt-1.5 text-[12px]">PDF 또는 XLSX · 최대 10MB</p>
          </>
        )}
      </label>

      {fileError ? (
        <p className="mt-4 rounded-2xl px-5 py-3.5 text-[13.5px]"
          style={{ background: "var(--color-accent-2-100)", color: "var(--color-accent-2-700)" }} role="alert">
          {fileError}
        </p>
      ) : null}

      {upload.error ? (
        <div className="mt-4">
          <ErrorView error={upload.error} />
        </div>
      ) : null}

      {uploaded ? (
        <div className="mt-7 flex flex-col gap-6 border-t pt-6" style={{ borderColor: "var(--line)" }}>
          {uploaded.parse_warnings.length > 0 ? (
            <ul className="flex flex-col gap-1 rounded-2xl px-5 py-3.5 text-[12px]"
              style={{ background: "var(--color-neutral-100)", color: "var(--color-neutral-800)" }}>
              {uploaded.parse_warnings.map((warning, index) => (
                <li key={`${warning.stage}-${index}`}>{warning.message}</li>
              ))}
            </ul>
          ) : null}

          {uploaded.parsed_candidates.length === 0 ? (
            // "개설과목 0개"(정상)와 "문서를 못 읽음"(PARSE_FAILED, 오류)은 다른 상황이다.
            <StateBlock
              title="문서에서 과목을 찾지 못했어요"
              description="편제표가 맞는지 확인하고 다시 올려주세요."
            />
          ) : (
            <>
              <div>
                <h3 className="mb-1 text-[17px]">이 과목들을 찾았어요</h3>
                <p className="sub mb-4">실제로 우리 학교에서 열리는 과목만 남기고 확정해주세요.</p>
                <ul className="space-y-2">
                  {selectable.map((candidate) => {
                    const subjectId = candidate.matched_subject_id as string;
                    const isChecked = checked.has(subjectId);
                    return (
                      <li key={subjectId}>
                        <label
                          className="flex cursor-pointer items-start gap-3 rounded-[18px] bg-white p-3.5 transition-colors"
                          style={{
                            boxShadow: isChecked
                              ? "inset 0 0 0 2px var(--accent)"
                              : "inset 0 0 0 1.5px var(--line)",
                            background: isChecked ? "var(--color-accent-100)" : "#fff",
                          }}
                        >
                          <input
                            type="checkbox"
                            checked={isChecked}
                            onChange={() =>
                              setChecked((prev) => {
                                const next = new Set(prev);
                                if (next.has(subjectId)) next.delete(subjectId);
                                else next.add(subjectId);
                                return next;
                              })
                            }
                            className="mt-1 size-4"
                            style={{ accentColor: "var(--accent)" }}
                          />
                          <span className="flex-1">
                            <span className="block font-semibold">{candidate.raw_text}</span>
                            <span className="mut mt-0.5 block text-[12px]">
                              {CONFIDENCE_NOTE[candidate.confidence]}
                            </span>
                          </span>
                          {candidate.confidence === "low" ? <Badge tone="blush">확인 필요</Badge> : null}
                        </label>
                      </li>
                    );
                  })}
                </ul>
              </div>

              {unresolved.length > 0 ? (
                <div>
                  <h3 className="mb-1 text-[17px]">자동으로 인식하지 못한 과목</h3>
                  <p className="sub mb-4">이 과목들은 지금은 확정할 수 없어요. 어떤 과목인지 직접 등록하는 기능은 준비 중이에요.</p>
                  <ul className="space-y-2">
                    {unresolved.map((candidate, index) => (
                      <li
                        key={`${candidate.raw_text}-${index}`}
                        className="mut rounded-2xl p-3.5 text-[13.5px]" style={{ background: "var(--color-neutral-100)" }}
                      >
                        {candidate.raw_text}
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}

              {confirm.error ? <ErrorView error={confirm.error} onRetry={() => confirm.reset()} /> : null}

              <Button className="w-full" onClick={() => void confirm.run()} disabled={confirm.pending}>
                {confirm.pending ? (
                  <Spinner label="확정하는 중" />
                ) : (
                  `${checked.size}개 과목으로 확정하기`
                )}
              </Button>
              {checked.size === 0 ? (
                <p className="mut text-center text-[12px]">
                  하나도 고르지 않고 확정하면 개설과목이 없는 것으로 처리돼요.
                </p>
              ) : null}
            </>
          )}
        </div>
      ) : null}
    </Card>
  );
}
