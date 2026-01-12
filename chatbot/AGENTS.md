# 챗봇 그래프 모듈 컨텍스트

## Module Context

이 모듈은 LangGraph 1.0+ 기반의 Router-Specialist 아키텍처 챗봇 시스템을 구현합니다.

**주요 컴포넌트:**

- **Graph Workflow**: `graph.py` - LangGraph 워크플로우 정의
- **Router Node**: `nodes/router.py` - 질문 분류 및 라우팅
- **Specialist Nodes**: `nodes/specialists/` - 전문가 에이전트 (FAQ, 트랜잭션, 단순 대화)
- **Deep Research Nodes**: `nodes/deep_research/` - 웹 검색 워크플로우 (Planner → Researcher → Grader → Writer)
- **Writer Node**: `nodes/writer.py` - 최종 답변 작성
- **Configuration**: `configuration.py` - 환경 변수 및 LLM 설정 관리
- **MongoDB Client**: `mongodb_client.py` - 대화 기록 저장
- **Vector Store**: `vector_store.py` - FAQ 벡터 검색

**의존성 관계:**

- `graph.py` → 모든 노드 모듈 의존
- 모든 노드 → `configuration.py` (설정 참조)
- Specialist 노드 → `vector_store.py`, `mongodb_client.py`
- Writer 노드 → `prompts/templates.py` (프롬프트 템플릿)

## Tech Stack & Constraints

### 필수 라이브러리

- **LangGraph**: 1.0.0+ (필수, 구버전 API 사용 금지)
- **LangChain**: 1.0.0+ (필수)
- **LangChain OpenAI**: 1.0.0+ (필수)
- **MongoDB (Motor)**: 3.0.0 (비동기 MongoDB 드라이버)
- **OpenAI**: 1.54.0+ (필수)

### 아키텍처 제약

1. **LangGraph 1.0+ API 필수**: `astream_events` 사용 시 `version="v2"` 지정 필수.
2. **비동기 처리**: 모든 I/O 작업 (MongoDB, Vector Store, HTTP 요청)은 `async/await` 사용.
3. **상태 관리**: `ChatState` (Pydantic 모델)로 상태를 명시적으로 관리.
4. **노드 패턴**: 모든 노드는 `async def node_function(state: ChatState) -> ChatState` 시그니처를 따릅니다.

### 사용 제한

- **절대 사용 금지**: LangGraph 0.x API 사용.
- **절대 사용 금지**: 동기 MongoDB 드라이버 (`pymongo` 직접 사용 금지, `motor` 사용 필수).
- **권장하지 않음**: `httpx` 대신 `requests` 사용 (비동기 처리 불가).

## Implementation Patterns

### 새 노드 추가 패턴

**1. 노드 함수 작성 (`nodes/your_node.py`):**

```python
from chatbot.models import ChatState
from chatbot.configuration import config
import logging

logger = logging.getLogger(__name__)

async def your_node(state: ChatState) -> ChatState:
    """노드 설명"""
    logger.info("노드 실행 시작")
    
    # 상태 읽기
    messages = state.get("messages", [])
    user_message = messages[-1].content if messages else ""
    
    # 노드 로직 수행
    # ...
    
    # 상태 업데이트
    state["your_field"] = result
    
    return state
```

**2. 그래프에 노드 추가 (`graph.py`):**

```python
from chatbot.nodes.your_node import your_node

# 노드 추가
workflow.add_node("your_node", your_node)

# 엣지 추가
workflow.add_edge("router", "your_node")
workflow.add_edge("your_node", "writer")
```

**3. 프롬프트 추가 (`prompts/templates.py`):**

필요 시 새 프롬프트 템플릿 함수를 추가하세요.

### 로깅 패턴

모든 노드에서 로깅을 적절히 수행하세요:

```python
import logging

logger = logging.getLogger(__name__)

# 로깅 (레벨별)
logger.debug("디버그 정보")
logger.info("일반 정보")
logger.warning("경고")
logger.error("오류", exc_info=True)
```

**로깅 레벨 제어**: 환경 변수 `LOG_LEVEL`로 제어 (DEBUG, INFO, WARNING, ERROR).

### 에러 처리 패턴

**MongoDB 연결 실패 시:**
- 서버 크래시 방지 (타임아웃 처리, 예외 처리)
- 경고 로그 출력 후 계속 진행

**LLM API 오류 시:**
- 명확한 에러 메시지 반환
- 사용자에게 친절한 오류 메시지 제공

## Testing Strategy

**테스트 명령어:**

```bash
# 단위 테스트
python -m pytest tests/test_chatbot.py

# 로깅 테스트
python -m pytest tests/test_logging.py
```

**테스트 작성 패턴:**

- 각 노드는 독립적으로 테스트 가능해야 함.
- `ChatState` 객체를 직접 생성하여 테스트.
- MongoDB 연결 없이도 테스트 가능하도록 모킹.

**로컬 테스트 환경:**

1. `.env` 파일에 테스트용 환경 변수 설정.
2. MongoDB Atlas 연결 확인 (또는 로컬 MongoDB).
3. OpenAI API 키 설정.

## Local Golden Rules

### 이 모듈에서 범하기 쉬운 실수

**1. LangGraph 구버전 API 사용:**

- **잘못된 예**: `graph.astream()` (구버전)
- **올바른 예**: `graph.astream_events(state, version="v2")` (LangGraph 1.0+)

**2. 동기 MongoDB 드라이버 사용:**

- **잘못된 예**: `pymongo.MongoClient()` (동기)
- **올바른 예**: `motor.motor_asyncio.AsyncIOMotorClient()` (비동기)

**3. 프롬프트에 JSON 구조 포함:**

- **잘못된 예**: 프롬프트에 JSON 형식 포함 → LLM이 JSON으로 응답
- **올바른 예**: 프롬프트에서 JSON 사용 금지 명시 → 자연어 응답만 생성

**4. 상태 업데이트 누락:**

- **잘못된 예**: 노드에서 상태를 읽기만 하고 업데이트하지 않음
- **올바른 예**: 항상 `return state`로 업데이트된 상태 반환

**5. 스트리밍에서 JSON 필터링 누락:**

- **잘못된 예**: LLM 응답의 JSON 구조를 그대로 스트리밍
- **올바른 예**: JSON 구조 자동 감지 및 필터링 후 토큰만 스트리밍

**6. 에러 처리 부족:**

- **잘못된 예**: MongoDB 연결 실패 시 서버 크래시
- **올바른 예**: 타임아웃 처리, 예외 처리, 경고 로그 후 계속 진행

**7. 환경 변수 직접 접근:**

- **잘못된 예**: `os.getenv("OPENAI_API_KEY")` 직접 호출
- **올바른 예**: `config.OPENAI_API_KEY` (중앙 관리)

### 권장 사항

- 새 노드 추가 시 기존 노드 패턴을 따르세요.
- 프롬프트 수정 시 `chatbot/prompts/templates.py`만 수정하세요.
- 설정 변경 시 `chatbot/configuration.py`만 수정하세요.
- 로깅은 모든 노드에서 적절히 수행하세요.
- 에러 발생 시 사용자에게 명확한 메시지를 제공하세요.
