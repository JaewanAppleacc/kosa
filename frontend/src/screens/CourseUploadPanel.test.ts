import { describe, expect, it } from "vitest";
import { validateFile } from "./CourseUploadPanel";

function fakeFile(name: string, size: number): File {
  const file = new File(["x"], name);
  Object.defineProperty(file, "size", { value: size });
  return file;
}

describe("업로드 파일 사전 검증", () => {
  it("PDF와 XLSX는 통과한다", () => {
    expect(validateFile(fakeFile("편제표.pdf", 1024))).toBeNull();
    expect(validateFile(fakeFile("편제표.XLSX", 1024))).toBeNull();
  });

  it("XLS는 XLSX로 다시 저장하라고 안내한다", () => {
    expect(validateFile(fakeFile("편제표.xls", 1024))).toContain("XLSX");
  });

  it("다른 형식은 거부한다", () => {
    expect(validateFile(fakeFile("편제표.hwp", 1024))).toContain("PDF");
  });

  it("빈 파일과 10MB 초과 파일은 올리기 전에 막는다", () => {
    expect(validateFile(fakeFile("빈파일.pdf", 0))).toContain("빈 파일");
    expect(validateFile(fakeFile("큰파일.pdf", 10 * 1024 * 1024 + 1))).toContain("10MB");
    expect(validateFile(fakeFile("경계.pdf", 10 * 1024 * 1024))).toBeNull();
  });
});
