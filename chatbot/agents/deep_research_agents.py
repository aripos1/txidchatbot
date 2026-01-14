"""
Deep Research 개별 노드 에이전트들
Planner, Researcher, Grader를 각각 독립적인 Agent로 구현
"""
import logging
from typing import List
from .base_agent import BaseAgent
from ..models import ChatState
from ..configuration import config
from ..nodes.deep_research import (
    planner as planner_func,
    researcher as researcher_func,
    grader as grader_func,
)

logger = logging.getLogger(__name__)


class PlannerAgent(BaseAgent):
    """Planner Agent - 검색 계획 수립"""
    
    def __init__(self):
        super().__init__(
            name="PlannerAgent",
            description="웹 검색 계획을 수립하는 에이전트"
        )
        self.update_state(
            plan_count=0,
            avg_query_count=0.0
        )
    
    async def process(self, state: ChatState) -> ChatState:
        """Planner 처리 로직 - 멀티 에이전트 협업"""
        import sys
        from langchain_core.messages import HumanMessage
        self.update_state(plan_count=self.get_state("plan_count", 0) + 1)
        
        # RouterAgent로부터 받은 정보 확인
        router_info = self.get_from_memory("shared_from_RouterAgent")
        if router_info:
            logger.info(f"📨 [{self.name}] RouterAgent로부터 정보 수신: {router_info.get('question_type', 'N/A')}")
            print(f"📨 [{self.name}] RouterAgent로부터 정보 수신: {router_info.get('question_type', 'N/A')}", file=sys.stdout, flush=True)
        
        # ✅ 시세 질문 조기 감지 (병렬 처리 불필요)
        user_messages = [msg for msg in state.get("messages", []) if isinstance(msg, HumanMessage)]
        if user_messages:
            last_message = user_messages[-1].content.lower()
            is_price_query = any(keyword in last_message for keyword in config.PRICE_KEYWORDS)
            
            if is_price_query:
                logger.info(f"✅ [{self.name}] 시세 질문 감지 - 단일 ResearcherAgent 호출 (병렬 처리 불필요)")
                print(f"✅ [{self.name}] 시세 질문 감지 - 단일 ResearcherAgent 호출", file=sys.stdout, flush=True)
                
                # Planner는 건너뛰고 바로 단일 ResearcherAgent 호출
                researcher_agent = ResearcherAgent()
                updated_state = await researcher_agent.process(state)
                
                # GraderAgent 호출 (직접 인스턴스 생성)
                grader_agent = GraderAgent()
                updated_state = await grader_agent.process(updated_state)
                
                return updated_state
        
        # 기존 Planner 함수 호출 (일반 질문)
        result = await planner_func(state)
        
        # ⚠️ 상태 손상 감지 (사용자 메시지 없음)
        if result.get("search_loop_count", 0) >= 999:
            logger.error("❌ [PlannerAgent] 상태 손상 감지 - 즉시 Fallback")
            print("❌ [PlannerAgent] 상태 손상 감지 - 즉시 Fallback", file=sys.stdout, flush=True)
            from ..nodes.writer import writer as writer_func
            fallback_state = {**state, **result}
            fallback_state = await writer_func(fallback_state)
            from ..nodes.save_response import save_response as save_response_func
            fallback_state = await save_response_func(fallback_state)
            return fallback_state
        
        # 쿼리 개수 기록
        search_queries = result.get("search_queries", [])
        if search_queries:
            query_count = len(search_queries)
            self.add_to_memory("last_query_count", query_count)
            
            # 평균 쿼리 개수 업데이트
            plan_count = self.get_state("plan_count", 1)
            avg_count = self.get_state("avg_query_count", 0.0)
            new_avg = (avg_count * (plan_count - 1) + query_count) / plan_count
            self.update_state(avg_query_count=new_avg)
            
            # ResearcherAgent에게 검색 계획 공유
            try:
                await self.share_info(
                    "ResearcherAgent",
                    {
                        "search_queries": search_queries,
                        "research_plan": result.get("research_plan", "")
                    },
                    result
                )
                logger.info(f"📨 [{self.name}] → [ResearcherAgent]: 검색 계획 공유 ({query_count}개 쿼리)")
            except Exception as e:
                logger.warning(f"⚠️ ResearcherAgent 정보 공유 실패: {e}")
        
        # 병렬 멀티 에이전트: 여러 ResearcherAgent 인스턴스를 병렬로 생성하여 실행
        updated_state = {**state, **result}
        
        search_queries = result.get("search_queries", [])
        
        # ⚠️ 검색 쿼리가 없으면 즉시 Fallback
        if not search_queries or len(search_queries) == 0:
            logger.warning("⚠️ [PlannerAgent] 검색 쿼리 없음 - 즉시 Fallback")
            print("⚠️ [PlannerAgent] 검색 쿼리 없음 - 즉시 Fallback", file=sys.stdout, flush=True)
            from ..nodes.writer import writer as writer_func
            updated_state = await writer_func(updated_state)
            from ..nodes.save_response import save_response as save_response_func
            updated_state = await save_response_func(updated_state)
            return updated_state
        
        if search_queries and len(search_queries) > 1:
            # 여러 쿼리가 있으면 각 쿼리마다 별도의 ResearcherAgent 인스턴스 생성하여 병렬 실행
            logger.info(f"🔀 [{self.name}] {len(search_queries)}개 쿼리 → {len(search_queries)}개 ResearcherAgent 병렬 실행")
            print(f"🔀 [{self.name}] {len(search_queries)}개 쿼리 → {len(search_queries)}개 ResearcherAgent 병렬 실행", file=sys.stdout, flush=True)
            
            import asyncio
            import uuid
            
            # 각 쿼리마다 별도의 ResearcherAgent 인스턴스 생성
            researcher_tasks = []
            for i, query in enumerate(search_queries):
                # 각 쿼리마다 새로운 ResearcherAgent 인스턴스 생성
                researcher_agent = ResearcherAgent(agent_id=str(uuid.uuid4())[:8])
                
                # 각 에이전트에 해당 쿼리만 할당
                query_state = {**updated_state, "search_queries": [query]}
                
                # 각 ResearcherAgent를 병렬로 실행
                researcher_tasks.append(researcher_agent.process(query_state))
            
            # 모든 ResearcherAgent를 병렬로 실행
            researcher_results = await asyncio.gather(*researcher_tasks, return_exceptions=True)
            
            # 결과 병합
            all_web_results = []
            all_messages = updated_state.get("messages", [])
            
            for i, result in enumerate(researcher_results):
                if isinstance(result, Exception):
                    logger.error(f"⚠️ [{self.name}] ResearcherAgent-{i} 실행 실패: {result}")
                    continue
                
                web_results = result.get("web_search_results", [])
                if web_results:
                    all_web_results.extend(web_results)
                
                # 메시지 병합 (중복 제거)
                result_messages = result.get("messages", [])
                for msg in result_messages:
                    if msg not in all_messages:
                        all_messages.append(msg)
            
            # 병합된 결과로 상태 업데이트
            updated_state["web_search_results"] = all_web_results
            updated_state["messages"] = all_messages
            
            logger.info(f"✅ [{self.name}] {len(researcher_tasks)}개 ResearcherAgent 병렬 실행 완료: {len(all_web_results)}개 결과 수집")
            print(f"✅ [{self.name}] {len(researcher_tasks)}개 ResearcherAgent 병렬 실행 완료: {len(all_web_results)}개 결과", file=sys.stdout, flush=True)
        else:
            # 단일 쿼리이거나 쿼리가 없으면 기존 방식대로 단일 ResearcherAgent 호출
            try:
                researcher_agent = ResearcherAgent()
                updated_state = await researcher_agent.process(updated_state)
            except Exception as e:
                logger.error(f"⚠️ [{self.name}] ResearcherAgent 호출 실패: {e}")
        
        # GraderAgent 호출 (모든 검색 완료 후) - 직접 인스턴스 생성
        try:
            grader_agent = GraderAgent()
            updated_state = await grader_agent.process(updated_state)
        except Exception as e:
            logger.error(f"⚠️ [{self.name}] GraderAgent 호출 실패: {e}")
        
        return updated_state
    
    def is_task_complete(self, state: ChatState) -> bool:
        """Planner 작업 완료 여부 자율 판단"""
        # Planner는 항상 ResearcherAgent를 호출해야 하므로 단독으로는 완료 불가
        return False
    
    def get_capabilities(self) -> List[str]:
        return [
            "검색 계획 수립",
            "검색 쿼리 생성",
            "연구 계획 작성"
        ]


class ResearcherAgent(BaseAgent):
    """Researcher Agent - 웹 검색 수행"""
    
    def __init__(self, agent_id: str = None):
        """ResearcherAgent 초기화
        
        Args:
            agent_id: 에이전트 고유 ID (여러 인스턴스 구분용)
        """
        agent_name = f"ResearcherAgent-{agent_id}" if agent_id else "ResearcherAgent"
        super().__init__(
            name=agent_name,
            description="웹 검색을 수행하는 에이전트"
        )
        self.agent_id = agent_id
        self.update_state(
            search_count=0,
            avg_result_count=0.0,
            google_count=0,
            duckduckgo_count=0
        )
    
    async def process(self, state: ChatState) -> ChatState:
        """Researcher 처리 로직 - 멀티 에이전트 협업"""
        import sys
        self.update_state(search_count=self.get_state("search_count", 0) + 1)
        
        # PlannerAgent로부터 받은 검색 계획 확인
        planner_info = self.get_from_memory("shared_from_PlannerAgent")
        if planner_info:
            logger.info(f"📨 [{self.name}] PlannerAgent로부터 검색 계획 수신")
            print(f"📨 [{self.name}] PlannerAgent로부터 검색 계획 수신 ({len(planner_info.get('search_queries', []))}개 쿼리)", file=sys.stdout, flush=True)
            # 검색 계획이 있으면 우선 사용
            if planner_info.get("search_queries"):
                state = {**state, "search_queries": planner_info["search_queries"]}
        
        # FAQAgent로부터 받은 정보 확인
        faq_info = self.get_from_memory("shared_from_FAQAgent")
        if faq_info:
            logger.info(f"📨 [{self.name}] FAQAgent로부터 위임 수신: {faq_info.get('reason', 'N/A')}")
            print(f"📨 [{self.name}] FAQAgent로부터 위임 수신: {faq_info.get('reason', 'N/A')}", file=sys.stdout, flush=True)
        
        # 기존 Researcher 함수 호출
        result = await researcher_func(state)
        
        # 검색 결과 기록
        web_search_results = result.get("web_search_results", [])
        if web_search_results:
            result_count = len(web_search_results)
            self.add_to_memory("last_result_count", result_count)
            
            # 평균 결과 개수 업데이트
            search_count = self.get_state("search_count", 1)
            avg_count = self.get_state("avg_result_count", 0.0)
            new_avg = (avg_count * (search_count - 1) + result_count) / search_count
            self.update_state(avg_result_count=new_avg)
            
            # 검색 엔진 통계
            for result_item in web_search_results:
                source = result_item.get("source", "")
                if "google" in source.lower():
                    self.update_state(google_count=self.get_state("google_count", 0) + 1)
                elif "duckduckgo" in source.lower() or "ddg" in source.lower():
                    self.update_state(duckduckgo_count=self.get_state("duckduckgo_count", 0) + 1)
        
        return result
    
    def is_task_complete(self, state: ChatState) -> bool:
        """Researcher 작업 완료 여부 자율 판단"""
        # Researcher는 검색 결과가 있어도 Grader의 평가가 필요하므로 단독으로는 완료 불가
        return False
    
    def get_capabilities(self) -> List[str]:
        return [
            "Google 검색",
            "DuckDuckGo 검색",
            "시세 API 조회",
            "검색 결과 수집"
        ]


class GraderAgent(BaseAgent):
    """Grader Agent - 검색 결과 평가"""
    
    def __init__(self):
        super().__init__(
            name="GraderAgent",
            description="검색 결과를 평가하는 에이전트"
        )
        self.update_state(
            grade_count=0,
            avg_score=0.0,
            sufficient_count=0
        )
    
    async def process(self, state: ChatState) -> ChatState:
        """Grader 처리 로직 - 멀티 에이전트 협업"""
        import sys
        self.update_state(grade_count=self.get_state("grade_count", 0) + 1)
        
        # 기존 Grader 함수 호출
        result = await grader_func(state)
        
        # 점수 기록
        grader_score = result.get("grader_score", 0.0)
        is_sufficient = result.get("is_sufficient", False)
        search_loop_count = state.get("search_loop_count", 0)
        
        self.add_to_memory("last_grader_score", grader_score)
        
        # 평균 점수 업데이트
        grade_count = self.get_state("grade_count", 1)
        avg_score = self.get_state("avg_score", 0.0)
        new_avg = (avg_score * (grade_count - 1) + grader_score) / grade_count
        self.update_state(avg_score=new_avg)
        
        # 충분한 결과 개수 업데이트
        if is_sufficient:
            self.update_state(sufficient_count=self.get_state("sufficient_count", 0) + 1)
        
        updated_state = {**state, **result}
        
        # 멀티 에이전트: 평가 결과에 따라 다음 단계 결정 (조건 분기)
        max_loops = 3
        web_search_results = updated_state.get("web_search_results", [])
        
        # ⚠️ 검색 결과가 없으면 즉시 Fallback (무한 루프 방지)
        if len(web_search_results) == 0 and search_loop_count > 0:
            logger.warning(f"⚠️ [{self.name}] 검색 결과 없음 - Writer 호출 (Fallback)")
            print(f"⚠️ [{self.name}] 검색 결과 없음 - Writer 호출 (Fallback)", file=sys.stdout, flush=True)
            from ..nodes.writer import writer as writer_func
            updated_state = await writer_func(updated_state)
            
            # Writer 완료 후 save_response 호출
            from ..nodes.save_response import save_response as save_response_func
            updated_state = await save_response_func(updated_state)
        elif is_sufficient and grader_score >= 0.7:
            # 결과 충분 → Writer 호출
            logger.info(f"✅ [{self.name}] 검색 결과 충분 (점수: {grader_score:.2f}) - Writer 호출")
            print(f"✅ [{self.name}] 검색 결과 충분 (점수: {grader_score:.2f}) - Writer 호출", file=sys.stdout, flush=True)
            from ..nodes.writer import writer as writer_func
            updated_state = await writer_func(updated_state)
            
            # Writer 완료 후 save_response 호출
            from ..nodes.save_response import save_response as save_response_func
            updated_state = await save_response_func(updated_state)
        elif search_loop_count < max_loops:
            # 결과 부족 → PlannerAgent 재호출 (재검색)
            logger.info(f"🔄 [{self.name}] 검색 결과 부족 (점수: {grader_score:.2f}) - PlannerAgent 재호출 (시도 {search_loop_count + 1}/{max_loops})")
            print(f"🔄 [{self.name}] 검색 결과 부족 (점수: {grader_score:.2f}) - PlannerAgent 재호출 (시도 {search_loop_count + 1}/{max_loops})", file=sys.stdout, flush=True)
            # search_loop_count 증가
            updated_state["search_loop_count"] = search_loop_count + 1
            try:
                updated_state = await self.call_agent("PlannerAgent", updated_state)
            except RecursionError as e:
                logger.error(f"⚠️ [{self.name}] Recursion Error 발생 - Writer Fallback: {e}")
                print(f"⚠️ [{self.name}] Recursion Error 발생 - Writer Fallback", file=sys.stdout, flush=True)
                from ..nodes.writer import writer as writer_func
                updated_state = await writer_func(updated_state)
                from ..nodes.save_response import save_response as save_response_func
                updated_state = await save_response_func(updated_state)
            except Exception as e:
                logger.error(f"⚠️ [{self.name}] PlannerAgent 재호출 실패 - Writer Fallback: {e}")
                print(f"⚠️ [{self.name}] PlannerAgent 재호출 실패 - Writer Fallback", file=sys.stdout, flush=True)
                from ..nodes.writer import writer as writer_func
                updated_state = await writer_func(updated_state)
                from ..nodes.save_response import save_response as save_response_func
                updated_state = await save_response_func(updated_state)
        else:
            # 최대 반복 초과 → Writer 호출 (Fallback)
            logger.warning(f"⚠️ [{self.name}] 검색 반복 초과 ({search_loop_count}회) - Writer 호출 (Fallback)")
            print(f"⚠️ [{self.name}] 검색 반복 초과 ({search_loop_count}회) - Writer 호출 (Fallback)", file=sys.stdout, flush=True)
            from ..nodes.writer import writer as writer_func
            updated_state = await writer_func(updated_state)
            
            # Writer 완료 후 save_response 호출
            from ..nodes.save_response import save_response as save_response_func
            updated_state = await save_response_func(updated_state)
        
        return updated_state
    
    def is_task_complete(self, state: ChatState) -> bool:
        """Grader 작업 완료 여부 자율 판단"""
        # Grader가 평가 후 Writer를 호출했으면 완료
        # Writer가 응답을 생성하고 save_response를 호출했는지 확인
        messages = state.get("messages", [])
        if messages:
            from langchain_core.messages import AIMessage
            # 최종 AI 응답이 있으면 완료
            ai_messages = [msg for msg in messages if isinstance(msg, AIMessage)]
            if ai_messages and len(ai_messages) > 1:  # RouterAgent 응답 + 최종 응답
                return True
        return False
    
    def get_capabilities(self) -> List[str]:
        return [
            "검색 결과 평가",
            "충분성 판단",
            "재검색 필요 여부 결정",
            "Writer 또는 PlannerAgent 자율 호출"
        ]


# 에이전트 인스턴스 생성 (싱글톤 패턴)
_planner_agent = None
_researcher_agent = None
_grader_agent = None


def get_planner_agent() -> PlannerAgent:
    """Planner 에이전트 인스턴스 가져오기"""
    global _planner_agent
    if _planner_agent is None:
        _planner_agent = PlannerAgent()
    return _planner_agent


def get_researcher_agent() -> ResearcherAgent:
    """Researcher 에이전트 인스턴스 가져오기"""
    global _researcher_agent
    if _researcher_agent is None:
        _researcher_agent = ResearcherAgent()
    return _researcher_agent


def get_grader_agent() -> GraderAgent:
    """Grader 에이전트 인스턴스 가져오기"""
    global _grader_agent
    if _grader_agent is None:
        _grader_agent = GraderAgent()
    return _grader_agent
