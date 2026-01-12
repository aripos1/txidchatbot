# 프롬프트 템플릿 모듈 컨텍스트

## Module Context

이 모듈은 모든 LLM 프롬프트 템플릿을 중앙에서 관리합니다.

**주요 컴포넌트:**

- **System Prompt**: `get_system_prompt_template()` - Writer 노드용 시스템 프롬프트
- **FAQ Prompt**: `get_faq_prompt_template()` - FAQ Specialist 노드용 프롬프트
- **Simple Chat Prompt**: `get_simple_chat_prompt()` - SimpleChat Specialist 노드용 프롬프트
- **Intent Clarification Prompt**: `get_intent_clarification_prompt()` - Intent Clarifier 노드용 프롬프트
- **Grader Prompt**: `get_grader_prompt()` - Grader 노드용 프롬프트
- **Planner Prompt**: `get_planner_prompt()` - Planner 노드용 프롬프트

**의존성 관계:**

- 모든 노드 → `prompts/templates.py` (프롬프트 템플릿 참조)
- 프롬프트 템플릿 → `configuration.py` (설정 참조, URL 등)

## Tech Stack & Constraints

### 프롬프트 규칙

1. **절대 위반 금지**: JSON 구조, 검색 쿼리, 연구 계획, 점수, 피드백 등 내부 처리 정보를 절대 포함하지 마세요.
2. **응답 형식**: 반드시 자연스러운 한국어 문장으로 시작하세요 (예: "현재 빗썸에서...", "빗썸의 주요 이벤트는...").
3. **번호 매기기**: 여러 항목을 나열할 때는 반드시 순차적인 번호를 사용하세요 (1. 2. 3. 4. 5. ...).
4. **URL 링크**: 마크다운 형식(`[텍스트](URL)`)을 절대 사용하지 마세요. 일반 텍스트로 작성하세요.

### 템플릿 구조

모든 프롬프트 템플릿은 Python 함수로 정의되며, `{variable_name}` 형식으로 변수를 사용합니다:

```python
def get_system_prompt_template() -> str:
    return """
    프롬프트 내용...
    {current_date_str} - 변수 예시
    """
```

**변수 치환**: 프롬프트 사용 시 `.format()` 또는 f-string으로 변수를 치환합니다.

## Implementation Patterns

### 새 프롬프트 추가 패턴

**1. 프롬프트 함수 추가 (`templates.py`):**

```python
def get_new_prompt_template() -> str:
    """새 노드용 프롬프트 템플릿 반환"""
    return """
    프롬프트 내용...
    {variable1}
    {variable2}
    """
```

**2. 노드에서 프롬프트 사용:**

```python
from chatbot.prompts.templates import get_new_prompt_template

prompt = get_new_prompt_template().format(
    variable1=value1,
    variable2=value2
)
```

### 프롬프트 수정 주의사항

**절대 지켜야 할 규칙:**

1. JSON 구조를 포함하지 마세요.
2. 번호 매기기를 중복하지 마세요 (1. 1. 1. 형식 금지).
3. URL 링크에 마크다운 형식을 사용하지 마세요.
4. 내부 처리 정보(검색 쿼리, 점수 등)를 포함하지 마세요.

**수정 예시:**

```python
# 잘못된 예
"""
다음 JSON 형식으로 응답하세요:
{
  "answer": "...",
  "sources": [...]
}
"""

# 올바른 예
"""
사용자 질문에 대해 명확하고 정확하게 답변하세요.
답변은 자연스러운 한국어 문장으로 작성하세요.
"""
```

## Testing Strategy

**테스트 방법:**

프롬프트는 직접 테스트하기 어려우므로, 실제 챗봇을 통해 테스트하세요:

```bash
# 서버 실행
python main.py

# 브라우저에서 챗봇 테스트
# http://localhost:8000/chat
```

**테스트 포인트:**

- LLM 응답에 JSON 구조가 포함되지 않는지 확인.
- 번호 매기기가 순차적으로 표시되는지 확인 (1. 2. 3. 형식).
- URL 링크가 올바르게 표시되는지 확인 (마크다운 형식 없음).
- 내부 처리 정보가 응답에 포함되지 않는지 확인.

## Local Golden Rules

### 이 모듈에서 범하기 쉬운 실수

**1. JSON 구조 포함:**

- **잘못된 예**: 프롬프트에 JSON 형식 요구 → LLM이 JSON으로 응답
- **올바른 예**: 자연어 응답만 요구 → JSON 사용 금지 명시

**2. 번호 매기기 중복:**

- **잘못된 예**: "1. 첫 번째\n1. 두 번째\n1. 세 번째" (중복)
- **올바른 예**: "1. 첫 번째\n2. 두 번째\n3. 세 번째" (순차적)

**3. URL 링크 마크다운 형식:**

- **잘못된 예**: `[빗썸 고객지원](https://support.bithumb.com/hc/ko)`
- **올바른 예**: `빗썸 고객지원 페이지: https://support.bithumb.com/hc/ko`

**4. 내부 처리 정보 포함:**

- **잘못된 예**: "검색 쿼리: 비트코인 시세", "점수: 0.85"
- **올바른 예**: 내부 처리 정보 없이 최종 답변만 제공

**5. 변수 치환 오류:**

- **잘못된 예**: `{variable}` 형식이 아닌 변수 사용
- **올바른 예**: `{variable_name}` 형식 사용, `.format()` 또는 f-string으로 치환

**6. 중복 함수 정의:**

- **잘못된 예**: 같은 함수를 두 번 정의 (중복)
- **올바른 예**: 함수는 한 번만 정의, 필요 시 수정

### 권장 사항

- 프롬프트 수정 시 모든 규칙을 다시 확인하세요.
- 새 프롬프트 추가 시 기존 프롬프트 패턴을 따르세요.
- 변수는 `{variable_name}` 형식으로 명확하게 명명하세요.
- 프롬프트 수정 후 실제 챗봇에서 테스트하세요.
- 규칙 위반 시 즉시 수정하세요 (중복 함수, JSON 구조 등).
