import { describe, expect, it } from "vitest";
import { ApiError, NetworkError, isApiError, parseErrorBody, toUserMessage } from "./errors";

describe("오류 본문 파싱", () => {
  it("서버 계약 형태({detail:{...}})를 ApiError로 바꾼다", () => {
    const error = parseErrorBody(
      { detail: { error_code: "EVIDENCE_NOT_READY", message: "아직 답변이 없습니다." } },
      422,
    );
    expect(error.code).toBe("EVIDENCE_NOT_READY");
    expect(error.status).toBe(422);
  });

  it("계약을 벗어난 응답(HTML 등)도 화면이 멈추지 않게 정규화한다", () => {
    const error = parseErrorBody("<html>502 Bad Gateway</html>", 502);
    expect(error.code).toBe("INTERNAL_ERROR");
    // 원본 본문을 사용자 문구에 그대로 노출하지 않는다.
    expect(error.message).not.toContain("html");
  });

  it("모르는 error_code는 통과시키지 않는다", () => {
    const error = parseErrorBody({ detail: { error_code: "NOPE", message: "?" } }, 400);
    expect(error.code).toBe("INTERNAL_ERROR");
  });
});

describe("isApiError", () => {
  it("코드까지 좁혀서 판별한다", () => {
    const error = new ApiError("SESSION_NOT_FOUND", "없음", 404);
    expect(isApiError(error, "SESSION_NOT_FOUND")).toBe(true);
    expect(isApiError(error, "PARSE_FAILED")).toBe(false);
    expect(isApiError(new NetworkError(null), "SESSION_NOT_FOUND")).toBe(false);
  });
});

describe("사용자 문구", () => {
  it("네트워크 오류에 내부 정보를 담지 않는다", () => {
    const message = toUserMessage(new NetworkError(new Error("ECONNREFUSED 127.0.0.1:8000")));
    expect(message).not.toContain("127.0.0.1");
    expect(message).not.toContain("ECONNREFUSED");
  });
});
