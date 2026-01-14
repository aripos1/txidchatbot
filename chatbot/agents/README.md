# 멀티 에이전트 아키텍처

이 디렉토리는 멀티 에이전트 아키텍처를 구현합니다. 기존 Router-Specialist 구조를 유지하면서 각 컴포넌트를 독립적인 에이전트로 변환했습니다.

## 구조

### BaseAgent
모든 에이전트의 기본 클래스로, 다음 기능을 제공합니다:
- **메모리 관리**: 에이전트별 메모리 저장 및 조회
- **상태 관리**: 에이전트별 상태 저장 및 업데이트
- **상호작용 기록**: 다른 에이전트와의 상호작용 기록

### 에이전트 목록

1. **RouterAgent** (`router_agent.py`)
   - 질문 분류 및 라우팅 담당
   - 규칙 기반 + LLM 기반 분류
   - 적절한 Specialist 에이전트로 라우팅

2. **FAQAgent** (`specialist_agents.py`)
   - FAQ 벡터 DB 검색
   - 빗썸 고객지원 페이지 검색
   - 날짜/시간 직접 답변
   - Hybrid 모드 위임

3. **TransactionAgent** (`specialist_agents.py`)
   - 트랜잭션 해시 감지
   - 31개 체인 멀티체인 조회
   - 트랜잭션 결과 포맷팅

4. **SimpleChatAgent** (`specialist_agents.py`)
   - 단순 대화 처리
   - 인사/감사 표현 응답
   - 대화 맥락 활용

5. **ResearchAgent** (`research_agent.py`)
   - 웹 검색 계획 수립
   - Google/DuckDuckGo 검색
   - 시세 API 조회
   - 검색 결과 평가
   - 답변 작성

## 기존 코드 호환성

기존 노드 함수들은 Agent를 래핑하여 호출하므로, 기존 그래프 구조는 그대로 유지됩니다:

```python
# 기존 코드
from chatbot.nodes import router, faq_specialist

# 내부적으로는 Agent를 사용
# router() → RouterAgent.process()
# faq_specialist() → FAQAgent.process()
```

## 에이전트 간 협업

에이전트들은 다음 방식으로 협업합니다:

1. **라우팅**: RouterAgent가 적절한 Specialist로 라우팅
2. **위임**: FAQAgent가 결과가 부족하면 ResearchAgent로 위임
3. **상호작용 기록**: 각 에이전트가 다른 에이전트와의 상호작용을 기록

## 사용 예시

```python
from chatbot.agents import get_faq_agent, get_router_agent

# 에이전트 인스턴스 가져오기
faq_agent = get_faq_agent()
router_agent = get_router_agent()

# 에이전트 직접 사용
state = await faq_agent.process(state)

# 통계 조회
stats = router_agent.get_routing_statistics()
```

## 확장 방법

새로운 에이전트를 추가하려면:

1. `BaseAgent`를 상속받는 클래스 생성
2. `process()` 메서드 구현
3. `can_handle()` 메서드로 처리 가능 여부 확인
4. `get_capabilities()` 메서드로 능력 목록 반환
5. 싱글톤 패턴으로 인스턴스 생성 함수 추가
