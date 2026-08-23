/**
 * 오류 표시 — error_code별로 학생이 다음에 뭘 하면 되는지까지 알려준다.
 * 서버 message를 그대로 쓰되, 개발자용 문구가 섞이는 코드에는 화면용 문구를 따로 쓴다.
 */
import { ApiError, ContractError, NetworkError, toUserMessage } from "@/api/errors";
import { Button, StateBlock } from "./ui";

function guidance(error: unknown): { title: string; description: string; retryable: boolean } {
  if (error instanceof ApiError) {
    switch (error.code) {
      case "EVIDENCE_NOT_READY":
        return {
          title: "아직 결과를 만들 답변이 모이지 않았어요",
          description: "질문에 조금 더 답하면 결과를 볼 수 있어요.",
          retryable: false,
        };
      case "SESSION_NOT_FOUND":
        return {
          title: "이 검사를 이어갈 수 없어요",
          description: "검사 기록이 남아 있지 않아요. 처음부터 다시 시작해주세요.",
          retryable: false,
        };
      case "MAJOR_NOT_SELECTABLE":
        return {
          title: "이 전공으로는 과목을 추천할 수 없어요",
          description: "지금 답변으로 추천된 전공 중에서 골라주세요.",
          retryable: false,
        };
      case "PARSE_FAILED":
        return {
          title: "문서를 읽지 못했어요",
          description:
            "사진으로 스캔한 PDF이거나 파일이 손상됐을 수 있어요. 글자를 선택할 수 있는 PDF나 XLSX로 다시 올려주세요.",
          retryable: false,
        };
      case "COURSE_UPLOAD_NOT_FOUND":
        return {
          title: "먼저 편제표를 올려주세요",
          description: "확정할 과목 목록이 아직 없어요.",
          retryable: false,
        };
      case "LLM_UNAVAILABLE":
        return {
          title: "잠시 준비 중이에요",
          description: "질문을 만드는 데 시간이 걸리고 있어요. 다시 시도해주세요.",
          retryable: true,
        };
      case "VALIDATION_ERROR":
        // 서버 message는 개발자용 문구(허용 목록·필드 경로 등)라 학생에게 그대로 보여주지
        // 않는다. 화면이 미리 막지 못한 조합이 넘어간 경우이므로 앞 단계로 안내한다.
        return {
          title: "이 조합으로는 진행할 수 없어요",
          description: "앞 화면으로 돌아가 다시 골라주세요.",
          retryable: false,
        };
      default:
        return { title: "문제가 생겼어요", description: error.message, retryable: true };
    }
  }
  if (error instanceof NetworkError) {
    return {
      title: "서버에 연결하지 못했어요",
      description: "네트워크 상태를 확인하고 다시 시도해주세요.",
      retryable: true,
    };
  }
  if (error instanceof ContractError) {
    return {
      title: "결과를 표시하지 못했어요",
      description: "잠시 후 다시 시도해주세요. 계속되면 담당자에게 알려주세요.",
      retryable: true,
    };
  }
  return { title: "알 수 없는 문제가 발생했어요", description: toUserMessage(error), retryable: true };
}

export function ErrorView({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const { title, description, retryable } = guidance(error);
  return (
    <StateBlock
      tone="error"
      title={title}
      description={description}
      action={
        retryable && onRetry ? (
          <Button variant="secondary" size="sm" onClick={onRetry}>
            다시 시도
          </Button>
        ) : null
      }
    />
  );
}
