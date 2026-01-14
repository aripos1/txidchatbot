# 자율 멀티 에이전트 시스템 마이그레이션 가이드

## 변경 사항 요약

### 1. CoordinatorAgent 역할 최소화
**Before:**
- 모든 에이전트 경로를 if-elif로 제어
- 각 단계마다 수동으로 다음 에이전트 호출
- 중앙 집중식 제어

**After:**
- 초기 RouterAgent 호출 및 첫 번째 에이전트 선택만
- 이후는 에이전트들이 완전 자율
- 분산 의사결정

### 2. BaseAgent에 is_task_complete() 추가
```python
def is_task_complete(self, state: ChatState) -> bool:
    """작업 완료 여부를 자율적으로 판단"""
    # 에이전트별로 override하여 구현
    pass
```

### 3. 각 Specialist Agent에 완료 판단 로직 추가
- `SimpleChatAgent`: AI 응답 생성 시 완료
- `FAQAgent`: DB 점수 >= 0.7 또는 웹 검색 완료 시
- `TransactionAgent`: 트랜잭션 결과 존재 시

### 4. Deep Research Agent 자율성 강화
- `PlannerAgent`: 여러 ResearcherAgent 병렬 생성
- `ResearcherAgent`: 다중 인스턴스 지원
- `GraderAgent`: Writer/PlannerAgent 자율 호출

## 설정 변경

### 환경 변수
```bash
# .env 파일
USE_TRUE_MULTI_AGENT=true  # 자율 모드 활성화
```

## 코드 변경 사항

### 1. CoordinatorAgent (coordinator_agent.py)
```python
# 변경 전
async def process(self, state: ChatState) -> ChatState:
    if question_type == "faq":
        await faq_agent.process(state)
        if needs_web_search:
            await planner_agent.process(state)
            # ... 더 많은 제어

# 변경 후
async def process(self, state: ChatState) -> ChatState:
    # Step 1: RouterAgent 호출
    state = await router_agent.process(state)
    
    # Step 2: 첫 번째 에이전트 선택
    first_agent = get_first_agent(question_type)
    
    # Step 3: 완전 위임
    state = await first_agent.process(state)
    return state
```

### 2. BaseAgent (base_agent.py)
```python
# 추가된 메서드
def is_task_complete(self, state: ChatState) -> bool:
    """작업 완료 여부 자율 판단"""
    messages = state.get("messages", [])
    if messages:
        from langchain_core.messages import AIMessage
        ai_messages = [msg for msg in messages if isinstance(msg, AIMessage)]
        if ai_messages:
            return True
    return False
```

### 3. Specialist Agents (specialist_agents.py)
```python
# FAQAgent에 추가
def is_task_complete(self, state: ChatState) -> bool:
    """FAQ 작업 완료 여부 자율 판단"""
    if state.get("needs_web_search", False):
        return False
    
    db_results = state.get("db_search_results", [])
    if db_results and len(db_results) > 0:
        best_score = db_results[0].get("score", 0)
        if best_score >= 0.7:
            return True
    
    return super().is_task_complete(state)
```

### 4. Deep Research Agents (deep_research_agents.py)
```python
# PlannerAgent 변경
async def process(self, state: ChatState) -> ChatState:
    result = await planner_func(state)
    updated_state = {**state, **result}
    
    search_queries = result.get("search_queries", [])
    if len(search_queries) > 1:
        # 여러 ResearcherAgent 인스턴스 병렬 생성
        researcher_tasks = []
        for query in search_queries:
            researcher_agent = ResearcherAgent(agent_id=uuid.uuid4())
            query_state = {**updated_state, "search_queries": [query]}
            researcher_tasks.append(researcher_agent.process(query_state))
        
        # 병렬 실행
        results = await asyncio.gather(*researcher_tasks)
        
        # 결과 병합
        all_web_results = []
        for result in results:
            web_results = result.get("web_search_results", [])
            if web_results:
                all_web_results.extend(web_results)
        
        updated_state["web_search_results"] = all_web_results
    
    # GraderAgent 자율 호출
    grader_agent = get_grader_agent()
    updated_state = await grader_agent.process(updated_state)
    
    return updated_state
```

## 테스트

### 1. 기본 테스트
```python
import asyncio
from chatbot.graph import get_chatbot_graph
from langchain_core.messages import HumanMessage

async def test_autonomous_multi_agent():
    graph = get_chatbot_graph()
    
    state = {
        "messages": [HumanMessage(content="안녕하세요")],
        "session_id": "test_session"
    }
    
    result = await graph.ainvoke(state)
    
    assert len(result["messages"]) > 1
    assert result.get("specialist_used") == "simple_chat"
    print("✅ SimpleChatAgent 테스트 통과")

asyncio.run(test_autonomous_multi_agent())
```

### 2. FAQ 테스트
```python
async def test_faq_agent():
    graph = get_chatbot_graph()
    
    state = {
        "messages": [HumanMessage(content="빗썸 출금 방법")],
        "session_id": "test_session"
    }
    
    result = await graph.ainvoke(state)
    
    assert result.get("specialist_used") == "faq"
    print("✅ FAQAgent 테스트 통과")

asyncio.run(test_faq_agent())
```

### 3. Deep Research 테스트 (병렬)
```python
async def test_deep_research_parallel():
    graph = get_chatbot_graph()
    
    state = {
        "messages": [HumanMessage(content="비트코인 2026년 전망")],
        "session_id": "test_session"
    }
    
    result = await graph.ainvoke(state)
    
    assert result.get("specialist_used") == "web_search"
    assert result.get("web_search_results") is not None
    print("✅ Deep Research 병렬 처리 테스트 통과")

asyncio.run(test_deep_research_parallel())
```

## 롤백 방법

자율 모드에서 하이브리드 모드로 돌아가려면:

```bash
# .env 파일
USE_TRUE_MULTI_AGENT=false
```

서버 재시작 후 기존 LangGraph 제어 방식으로 복귀됩니다.

## 주의사항

1. **환경 변수 필수**: `USE_TRUE_MULTI_AGENT=true` 설정 필요
2. **서버 재시작**: 환경 변수 변경 후 서버 재시작 필요
3. **로그 확인**: 자율 모드에서는 로그가 더 상세함
4. **병렬 처리**: 검색 속도는 빨라지지만 API 호출 증가

## 문제 해결

### Q: 에이전트가 무한 루프에 빠집니다
A: `is_task_complete()`가 항상 False를 반환하는지 확인하세요.

### Q: 병렬 처리가 작동하지 않습니다
A: `asyncio.gather()`가 올바르게 사용되었는지 확인하세요.

### Q: 에이전트가 다음 에이전트를 호출하지 않습니다
A: `call_agent()` 메서드가 올바르게 호출되었는지 확인하세요.

## 추가 리소스

- [AUTONOMOUS_MULTI_AGENT.md](./AUTONOMOUS_MULTI_AGENT.md) - 상세 아키텍처
- [README.md](./README.md) - 에이전트 목록 및 기본 사용법
- [base_agent.py](./base_agent.py) - BaseAgent 구현

## 지원

문제가 발생하면 다음을 확인하세요:
1. 환경 변수 설정
2. 로그 파일 (`LOG_LEVEL=DEBUG` 설정)
3. 에이전트별 is_task_complete() 구현
4. 에이전트 간 호출 체인
