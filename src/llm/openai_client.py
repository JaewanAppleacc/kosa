"""ChatLLMClient Protocol의 실제 구현체 — OpenAI 공식 SDK로 mlapi.run 호환 엔드포인트를
호출한다 (Base URL·모델은 .env, src/llm/settings.py 참고). 이 파일은 Adapter이므로 얇게
유지한다 — 질문 생성 로직(§10)은 여기 두지 않는다.
"""

from __future__ import annotations

from openai import OpenAI

from src.llm.protocols import LLMCallError, ModelT
from src.llm.settings import ChatLLMSettings


class OpenAIChatClient:
    def __init__(self, settings: ChatLLMSettings) -> None:
        self._client = OpenAI(base_url=settings.base_url, api_key=settings.api_key)
        self._model = settings.model

    def complete_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: type[ModelT],
    ) -> ModelT:
        try:
            response = self._client.chat.completions.parse(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format=response_model,
            )
        except Exception as exc:  # 원인 보존 — 조용히 삼키지 않는다 (CLAUDE.md)
            raise LLMCallError(f"LLM 호출 실패: {exc}") from exc

        parsed = response.choices[0].message.parsed
        if parsed is None:
            raise LLMCallError(
                "LLM이 response_format에 맞는 구조화된 출력을 반환하지 않았습니다."
            )
        return parsed
