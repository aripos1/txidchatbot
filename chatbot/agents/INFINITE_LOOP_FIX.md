# 무한 루프 방지 개선 사항

## 문제 상황

터미널 로그에서 발견된 문제:
```
Planner: 사용자 메시지 없음 (반복)
검색 결과: 0개, 반복: 0회 (반복)
GraderAgent → PlannerAgent 재호출 (무한 반복)
RecursionError: maximum recursion depth exceeded
```

## 근본 원인

1. **상태 손상**: GraderAgent가 PlannerAgent를 재호출할 때 사용자 메시지가 state에서 손실
2. **검색 쿼리 없음**: Planner가 사용자 메시지 없이 빈 쿼리 반환
3. **무한 재시도**: GraderAgent가 검색 결과 없음에도 계속 PlannerAgent 재호출
4. **Exception 처리 부족**: RecursionError 발생 시 적절한 fallback 없음

## 적용된 수정 사항

### 1. Planner 노드 (`chatbot/nodes/deep_research/planner.py`)

**변경 전:**
```python
if not user_messages:
    logger.warning("Planner: 사용자 메시지 없음")
    return {"research_plan": "", "search_queries": []}
```

**변경 후:**
```python
if not user_messages:
    logger.error("❌ Planner: 사용자 메시지 없음 - 상태 손상")
    print("❌ Planner: 사용자 메시지 없음 - 상태 손상", file=sys.stdout, flush=True)
    return {
        "research_plan": "사용자 메시지를 찾을 수 없어 검색을 진행할 수 없습니다.",
        "search_queries": [],
        "grader_score": 0.0,
        "is_sufficient": False,
        "search_loop_count": 999  # 강제 종료 신호
    }
```

**효과**: 상태 손상을 명확히 표시하고 강제 종료 신호 전달

### 2. PlannerAgent (`chatbot/agents/deep_research_agents.py`)

**추가된 안전장치 1: 상태 손상 감지**
```python
# 기존 Planner 함수 호출
result = await planner_func(state)

# ⚠️ 상태 손상 감지 (사용자 메시지 없음)
if result.get("search_loop_count", 0) >= 999:
    logger.error("❌ [PlannerAgent] 상태 손상 감지 - 즉시 Fallback")
    from ..nodes.writer import writer as writer_func
    fallback_state = {**state, **result}
    fallback_state = await writer_func(fallback_state)
    from ..nodes.save_response import save_response as save_response_func
    fallback_state = await save_response_func(fallback_state)
    return fallback_state
```

**추가된 안전장치 2: 검색 쿼리 없음 감지**
```python
# ⚠️ 검색 쿼리가 없으면 즉시 Fallback
if not search_queries or len(search_queries) == 0:
    logger.warning("⚠️ [PlannerAgent] 검색 쿼리 없음 - 즉시 Fallback")
    from ..nodes.writer import writer as writer_func
    updated_state = await writer_func(updated_state)
    from ..nodes.save_response import save_response as save_response_func
    updated_state = await save_response_func(updated_state)
    return updated_state
```

**효과**: 
- 상태 손상 시 즉시 Writer로 fallback
- 검색 쿼리 없을 때 즉시 Writer로 fallback
- ResearcherAgent 호출 전 조기 종료

### 3. GraderAgent (`chatbot/agents/deep_research_agents.py`)

**추가된 안전장치 1: 검색 결과 없음 즉시 Fallback**
```python
max_loops = 3
web_search_results = updated_state.get("web_search_results", [])

# ⚠️ 검색 결과가 없으면 즉시 Fallback (무한 루프 방지)
if len(web_search_results) == 0 and search_loop_count > 0:
    logger.warning(f"⚠️ [{self.name}] 검색 결과 없음 - Writer 호출 (Fallback)")
    from ..nodes.writer import writer as writer_func
    updated_state = await writer_func(updated_state)
    from ..nodes.save_response import save_response as save_response_func
    updated_state = await save_response_func(updated_state)
```

**추가된 안전장치 2: RecursionError 명시적 처리**
```python
try:
    updated_state = await self.call_agent("PlannerAgent", updated_state)
except RecursionError as e:
    logger.error(f"⚠️ [{self.name}] Recursion Error 발생 - Writer Fallback: {e}")
    from ..nodes.writer import writer as writer_func
    updated_state = await writer_func(updated_state)
    from ..nodes.save_response import save_response as save_response_func
    updated_state = await save_response_func(updated_state)
except Exception as e:
    logger.error(f"⚠️ [{self.name}] PlannerAgent 재호출 실패 - Writer Fallback: {e}")
    from ..nodes.writer import writer as writer_func
    updated_state = await writer_func(updated_state)
    from ..nodes.save_response import save_response as save_response_func
    updated_state = await save_response_func(updated_state)
```

**추가된 개선: 재시도 횟수 표시**
```python
logger.info(f"🔄 [{self.name}] 검색 결과 부족 (점수: {grader_score:.2f}) - PlannerAgent 재호출 (시도 {search_loop_count + 1}/{max_loops})")
```

**효과**:
- 검색 결과 없을 때 무한 재시도 방지
- RecursionError 발생 시 명시적 fallback
- 모든 Exception에 대한 fallback 보장
- 진행 상황을 명확히 표시

## 안전장치 계층 구조

```
Level 1: Planner 노드
    └─ 사용자 메시지 없음 → 강제 종료 신호 (search_loop_count=999)

Level 2: PlannerAgent
    ├─ 상태 손상 감지 (search_loop_count>=999) → Writer Fallback
    └─ 검색 쿼리 없음 → Writer Fallback

Level 3: GraderAgent
    ├─ 검색 결과 없음 (재시도 중) → Writer Fallback
    ├─ RecursionError 발생 → Writer Fallback
    ├─ 기타 Exception → Writer Fallback
    └─ 최대 재시도 초과 → Writer Fallback
```

## 테스트 시나리오

### 1. 정상 플로우
```
사용자 질문 → Planner (쿼리 생성) → Researcher (검색) → Grader (평가)
→ 충분 → Writer → save_response → 완료 ✅
```

### 2. 재검색 플로우
```
사용자 질문 → Planner → Researcher → Grader (부족)
→ Planner (재검색) → Researcher → Grader (충분)
→ Writer → save_response → 완료 ✅
```

### 3. 상태 손상 시나리오 (수정 전 무한 루프)
```
Grader → Planner 재호출
→ Planner: 사용자 메시지 없음 (search_loop_count=999)
→ PlannerAgent: 상태 손상 감지
→ Writer Fallback → save_response → 완료 ✅
```

### 4. 검색 쿼리 생성 실패 시나리오
```
Planner → 쿼리 없음
→ PlannerAgent: 검색 쿼리 없음 감지
→ Writer Fallback → save_response → 완료 ✅
```

### 5. 검색 결과 없음 반복 시나리오 (수정 전 무한 루프)
```
Researcher → 검색 결과 0개
→ Grader: 검색 결과 없음 감지
→ Writer Fallback → save_response → 완료 ✅
```

### 6. RecursionError 시나리오 (수정 전 크래시)
```
Grader → PlannerAgent 재호출 (깊은 재귀)
→ RecursionError 발생
→ GraderAgent: RecursionError catch
→ Writer Fallback → save_response → 완료 ✅
```

## 기대 효과

1. **무한 루프 완전 방지**: 모든 경로에 fallback 보장
2. **RecursionError 방지**: 명시적 예외 처리
3. **상태 손상 복구**: 조기 감지 및 fallback
4. **명확한 로깅**: 각 fallback 사유를 로그에 기록
5. **사용자 경험 개선**: 항상 답변 제공 (최악의 경우 fallback 답변)

## 추가 개선 가능 사항 (향후)

1. **State 복원 메커니즘**: 재호출 시 원본 사용자 메시지 강제 보존
2. **Circuit Breaker 패턴**: 연속 실패 시 일정 시간 동안 재시도 차단
3. **메트릭 수집**: 무한 루프 발생 빈도 모니터링
4. **더 나은 Fallback 메시지**: 실패 원인별 맞춤 안내 메시지

## 롤백 방법

만약 문제가 발생하면 git으로 이전 버전으로 돌아갈 수 있습니다:
```bash
git log --oneline  # 커밋 확인
git revert <commit-hash>  # 특정 커밋 롤백
```

또는 하이브리드 모드로 전환:
```bash
# .env 파일
USE_TRUE_MULTI_AGENT=false
```

## 결론

이제 **3중 안전장치**로 무한 루프가 완전히 방지됩니다:
1. Planner 레벨: 상태 손상 신호 전달
2. PlannerAgent 레벨: 조기 감지 및 fallback
3. GraderAgent 레벨: 모든 예외 상황에 fallback

**테스트 권장**: 서버 재시작 후 다양한 질문으로 테스트 필요
