# 멀티 에이전트 협업 시스템

## 개요

이 시스템은 **규칙 기반 멀티 에이전트 협업 아키텍처**를 구현합니다. 각 에이전트는 정해진 역할을 수행하며, 에이전트 간 협업을 통해 복잡한 작업을 처리합니다.

**핵심 특징:**
- ✅ **병렬 처리**: 여러 ResearcherAgent를 동시에 실행하여 검색 속도 향상
- ✅ **에이전트 협업**: 에이전트 간 정보 공유 및 순차적 협업
- ✅ **구조화된 워크플로우**: Router → Specialist → Deep Research (필요 시) 패턴
- ⚠️ **부분적 자율성**: 조건 분기는 있지만, 전체 흐름은 미리 정의됨

## 핵심 원칙

### 1. **구조화된 협업**
- `CoordinatorAgent`는 초기 라우팅 담당
- 이후 각 에이전트는 **정해진 순서대로** 다음 에이전트 호출
- **고정된 워크플로우**: Planner → Researcher → Grader → Writer

### 2. **조건 분기 (제한적)**
```python
# 에이전트는 조건에 따라 다음 경로 선택 (미리 정의된 옵션 중)
# 예: GraderAgent
if score >= 0.7:
    await self.call_agent("Writer", state)  # 옵션 1
else:
    await self.call_agent("PlannerAgent", state)  # 옵션 2 (재검색)
```

### 3. **에이전트 간 협업**
```python
# 에이전트 간 직접 호출
await self.call_agent("OtherAgent", state)

# 병렬 실행
await self.call_agents_parallel(["Agent1", "Agent2"], state)

# 정보 공유
await self.share_info("OtherAgent", data, state)

# 작업 위임
await self.delegate("OtherAgent", reason, state)
```

### 4. **병렬 처리 (실제 구현됨)** ✅
- PlannerAgent가 여러 ResearcherAgent 인스턴스 생성
- 각 인스턴스가 독립적인 검색 쿼리 처리
- `asyncio.gather()`로 병렬 실행
- 결과 자동 병합

## 워크플로우

### 전체 구조 (고정된 흐름)
```
사용자 질문
    ↓
CoordinatorAgent
    ↓
RouterAgent (질문 분류)
    ↓
첫 번째 Specialist 선택 (if-else 규칙)
    ├─ SimpleChatAgent → save_response
    ├─ TransactionAgent → save_response
    ├─ FAQAgent → (충분?) save_response / (부족?) PlannerAgent
    └─ PlannerAgent → Researcher(병렬) → Grader → Writer → save_response
```

### 에이전트 협업 패턴
```
SimpleChatAgent
    → 답변 생성
    → save_response 호출 (고정된 다음 단계)
    → 완료

FAQAgent
    → DB 검색
    → if (score >= 0.7): save_response → 완료
    → else: PlannerAgent 호출 (규칙 기반 분기)
        → PlannerAgent → ResearcherAgent(들) 병렬 실행 ✅
        → GraderAgent → 평가
        → if (score >= 0.7): Writer → save_response → 완료
        → else if (반복 < 3): PlannerAgent 재호출 (재검색)
        → else: Writer Fallback → 완료

TransactionAgent
    → 트랜잭션 조회
    → save_response 호출 (고정된 다음 단계)
    → 완료

PlannerAgent (실제 병렬 처리) ✅
    → 검색 계획 수립 (LLM이 쿼리 생성)
    → 여러 ResearcherAgent 인스턴스 생성 (예: 7개)
    → asyncio.gather()로 병렬 실행
    → 결과 병합
    → GraderAgent 호출 (고정된 다음 단계)
```

## 에이전트 목록

### 1. **CoordinatorAgent** (조율자)
- 역할: RouterAgent 호출 → 첫 번째 에이전트 선택
- 선택 방식: **if-else 규칙** (question_type에 따라 하드코딩)
- 이후: 선택된 에이전트가 정해진 워크플로우 실행

### 2. **RouterAgent** (분류기)
- 역할: LLM으로 질문 분류 (simple_chat, faq, transaction, web_search)
- 협업: 다른 에이전트에게 정보 공유 (`share_info`) ✅

### 3. **Specialist Agents**

#### SimpleChatAgent
- 역할: 단순 대화 처리 (인사, 감사 등)
- 다음 단계: save_response (고정)
- 완료 판단: AI 응답 생성 시 완료

#### FAQAgent
- 역할: FAQ 벡터 DB 검색 (빗썸 FAQ)
- 조건 분기: 
  - `if score >= 0.7`: save_response 호출
  - `else`: PlannerAgent 호출 (웹 검색으로 보완)
- 완료 판단: DB 점수 >= 0.7 또는 웹 검색 완료 시

#### TransactionAgent
- 역할: 블록체인 트랜잭션 조회 (31개 체인)
- 다음 단계: save_response (고정)
- 완료 판단: 트랜잭션 결과 존재 시

### 4. **Deep Research Agents**

#### PlannerAgent ✅ (병렬 처리 핵심)
- 역할: LLM으로 검색 계획 수립 (쿼리 생성)
- **병렬 처리 구현**: 
  - 여러 ResearcherAgent 인스턴스 생성 (예: 7개)
  - 각 쿼리마다 별도 에이전트 할당
  - `asyncio.gather()`로 병렬 실행 ✅
  - 결과 자동 병합
- 다음 단계: GraderAgent (고정)

#### ResearcherAgent ✅ (병렬 실행됨)
- 역할: 웹 검색 수행 (Google, DuckDuckGo) + 시세 API 조회
- **병렬 실행**: PlannerAgent가 여러 인스턴스를 동시에 실행 ✅
- 검색 엔진: Google + DuckDuckGo 병렬 검색
- 다음 단계: 결과를 PlannerAgent로 반환 (병합)

#### GraderAgent
- 역할: LLM으로 검색 결과 평가 (0.0 ~ 1.0 점수)
- 조건 분기:
  - `if score >= 0.7`: Writer 호출
  - `else if 반복 < 3`: PlannerAgent 재호출 (재검색)
  - `else`: Writer 호출 (Fallback)
- 완료 판단: Writer가 최종 응답 생성 시

## 병렬 처리 (실제 구현) ✅

### 실제 로그 기반 예시 (비트코인 시세 질문)

**터미널 로그:**
```
2026-01-13 07:09:34 - [PlannerAgent] 7개 쿼리 → 7개 ResearcherAgent 병렬 실행
2026-01-13 07:09:34 - Researcher 노드 시작 (7개 동시)
2026-01-13 07:09:40 - [PlannerAgent] 7개 ResearcherAgent 병렬 실행 완료: 7개 결과 수집
```

### 실제 코드 (PlannerAgent)
```python
# PlannerAgent가 7개 쿼리 생성 (LLM)
search_queries = [
    "비트코인 시세", "BTC 가격", "Bitcoin price KRW", 
    # ... 총 7개
]

# 각 쿼리마다 별도의 ResearcherAgent 인스턴스 생성
researcher_tasks = []
for query in search_queries:
    researcher_agent = ResearcherAgent(agent_id=uuid.uuid4())
    query_state = {**state, "search_queries": [query]}
    researcher_tasks.append(researcher_agent.process(query_state))

# asyncio.gather()로 병렬 실행 ✅
results = await asyncio.gather(*researcher_tasks)
# 결과: 7개 ResearcherAgent가 동시에 실행되어 약 6초 소요
```

### 검색 엔진 병렬 실행 (각 ResearcherAgent 내부)
```python
# 각 ResearcherAgent가 Google + DuckDuckGo 동시 실행
google_task = _search_with_google(queries)
duckduckgo_task = _search_with_duckduckgo(queries)

results = await asyncio.gather(google_task, duckduckgo_task)
```

**성능:** 7개 쿼리 순차 실행 시 ~42초 → 병렬 실행 시 ~6초 (7배 빠름) ✅

## 환경 변수

```bash
# 멀티 에이전트 협업 모드 선택
USE_TRUE_MULTI_AGENT=true
```

**모드 비교:**
- `true`: CoordinatorAgent가 에이전트 간 협업 관리 (권장)
  - 장점: 에이전트 간 정보 공유, 병렬 처리 최적화
  - 워크플로우: Coordinator → Router → Specialist → (협업)
  
- `false`: LangGraph가 그래프 엣지로 워크플로우 제어
  - 장점: 시각화 가능, 디버깅 쉬움
  - 워크플로우: 그래프 엣지로 고정된 경로

**⚠️ 두 모드 모두 고정된 워크플로우를 따릅니다.** 차이는 제어 주체일 뿐입니다.

## 장점

### 1. **병렬 처리로 성능 향상** ✅
- 여러 ResearcherAgent 동시 실행
- 검색 속도 7배 향상 (7개 쿼리 기준)
- 효율적인 리소스 활용 (`asyncio.gather()`)

### 2. **구조화된 협업** ✅
- 에이전트 간 명확한 역할 분담
- 정보 공유 메커니즘 (`share_info`)
- 순차적 협업으로 복잡한 작업 처리

### 3. **조건부 분기** ⚠️
- GraderAgent: 점수에 따라 Writer 또는 재검색
- FAQAgent: DB 결과에 따라 완료 또는 웹 검색
- 한정된 옵션 중 선택 (완전한 자율은 아님)

### 4. **확장성** ✅
- 새로운 Specialist 쉽게 추가
- 기존 에이전트 수정 없이 확장
- 모듈식 구조

### 5. **안전장치** ✅
- 무한 루프 방지 (최대 3회 재검색)
- Fallback 메커니즘 (검색 실패 시 Writer로 강제 이동)
- RecursionError 방지

## 개선 사항 (이전 대비)

### Before (단일 노드)
```python
# 단일 노드에서 모든 로직 처리
async def researcher_node(state):
    queries = ["쿼리1", "쿼리2", "쿼리3"]
    results = []
    for query in queries:
        result = await search(query)  # 순차 실행 (느림)
        results.append(result)
    return {"results": results}
```

### After (멀티 에이전트 + 병렬)
```python
# 여러 에이전트가 협업 + 병렬 실행
async def planner_agent(state):
    queries = ["쿼리1", "쿼리2", "쿼리3"]
    
    # 여러 ResearcherAgent 생성
    tasks = [ResearcherAgent().process({**state, "queries": [q]}) 
             for q in queries]
    
    # 병렬 실행 ✅
    results = await asyncio.gather(*tasks)
    return {"results": results}
```

**개선 효과:**
- 성능: 7배 빠름 (병렬 처리)
- 코드: 역할별 분리로 가독성 향상
- 유지보수: 각 에이전트 독립적으로 수정 가능

## 실제 실행 예시 (터미널 로그 기반)

```python
# 챗봇 그래프 생성 (환경 변수 USE_TRUE_MULTI_AGENT=true)
graph = create_chatbot_graph()

# 질문 처리
state = {
    "messages": [HumanMessage(content="오늘 비트코인 시세 알려줘")],
    "session_id": "session_123"
}

# 실제 워크플로우 (2026-01-13 로그 기준)
result = await graph.ainvoke(state)
```

**실제 실행 순서 (터미널 로그):**
```
1. CoordinatorAgent → RouterAgent 호출
   로그: "🚀 멀티 에이전트 협업 시스템 시작"

2. RouterAgent → "web_search" 분류 (LLM 판단)
   로그: "[RouterAgent] → [PlannerAgent]: 라우팅 정보 공유"

3. CoordinatorAgent → PlannerAgent에게 위임 (if-else 규칙)
   로그: "🎯 Step 2: PlannerAgent에게 작업 위임"

4. PlannerAgent → 7개 검색 쿼리 생성 (LLM)
   로그: "[Planner] ✅ 검색 계획 수립 완료: 쿼리 7개"

5. PlannerAgent → 7개 ResearcherAgent 병렬 생성 및 실행 ✅
   로그: "🔀 [PlannerAgent] 7개 쿼리 → 7개 ResearcherAgent 병렬 실행"
   시간: ~6초 (병렬 실행으로 효율적)

6. ResearcherAgent들 → 시세 API 조회 (각각)
   로그: "[Researcher] ✅ 1개 코인 시세 조회 완료" (7번 반복)
   결과: "BTC = 133,642,237.74 KRW"

7. GraderAgent → 결과 평가 (점수: 0.95)
   로그: "[Grader] ✅ 시세 API 결과 - 자동 합격"
   판단: score >= 0.7 → Writer 호출

8. Writer → 최종 답변 작성 (LLM)
   로그: "[Writer] ✅ 완료 (길이: 84자)"

9. 완료
   로그: "✅ 멀티 에이전트 협업 워크플로우 완료"
   총 소요 시간: ~17초
```

**핵심 특징:**
- ✅ 고정된 순서를 따름 (예측 가능)
- ✅ 병렬 처리로 효율성 향상 (7배 빠름)
- ✅ 조건 분기로 유연성 제공 (제한적)
- ✅ 안전장치로 안정성 확보

## 통계 및 모니터링

각 에이전트는 자신의 통계를 관리합니다:

```python
# 에이전트 통계 조회
faq_agent = get_faq_agent()
stats = {
    "search_count": faq_agent.get_state("search_count"),
    "success_count": faq_agent.get_state("success_count"),
    "avg_score": faq_agent.get_state("avg_score")
}

# 에이전트 상호작용 기록
interactions = faq_agent.interaction_history
```

## 결론

이 시스템은 **규칙 기반 멀티 에이전트 협업 시스템**입니다:

### ✅ 실제로 구현된 것
- ✅ **병렬 처리**: 7개 ResearcherAgent 동시 실행으로 7배 성능 향상
- ✅ **에이전트 협업**: 정보 공유 및 순차적 협업 패턴
- ✅ **조건 분기**: 점수/결과에 따라 다음 경로 선택
- ✅ **안전장치**: 무한 루프 방지, Fallback 메커니즘
- ✅ **모듈식 구조**: 역할별 분리로 확장 용이

### ❌ 구현되지 않은 것
- ❌ **완전한 자율성**: 실제로는 고정된 워크플로우 (if-else 규칙)
- ❌ **동적 워크플로우**: 미리 정의된 경로만 가능
- ❌ **LLM 기반 에이전트 선택**: CoordinatorAgent는 규칙 기반

### 🎯 시스템 분류
- **일반 챗봇** (1점) ❌
- **규칙 기반 워크플로우** (2점) ❌
- **멀티 에이전트 협업** (3점) ✅ ← **현재 위치**
- **하이브리드 자율** (4점) ❌
- **완전 자율 에이전트** (5점) ❌

**현실적 평가: 3.5/5.0 ⭐⭐⭐★☆**
- 장점: 병렬 처리, 구조화된 협업, 안정성
- 한계: 고정된 워크플로우, 제한적 자율성
- 적합: 프로덕션 환경, 예측 가능한 동작 필요 시
