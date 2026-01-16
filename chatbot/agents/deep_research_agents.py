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
        """Planner 처리 로직 - LangGraph 그래프를 통해 실행됨"""
        import sys
        from langchain_core.messages import HumanMessage
        self.update_state(plan_count=self.get_state("plan_count", 0) + 1)
        
        # CoordinatorAgent(router)로부터 받은 정보 확인
        router_info = self.get_from_memory("shared_from_RouterAgent")
        if router_info:
            logger.info(f"📨 [{self.name}] Coordinator(router)로부터 정보 수신: {router_info.get('question_type', 'N/A')}")
            print(f"📨 [{self.name}] Coordinator(router)로부터 정보 수신: {router_info.get('question_type', 'N/A')}", file=sys.stdout, flush=True)
        
        # 기존 Planner 함수 호출만 수행 (LangGraph 그래프가 이후 흐름을 관리)
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
            fallback_state["writer_executed"] = True
            return fallback_state
        
        # ⚠️ 검색 쿼리가 없으면 즉시 Fallback
        search_queries = result.get("search_queries", [])
        if not search_queries or len(search_queries) == 0:
            logger.warning("⚠️ [PlannerAgent] 검색 쿼리 없음 - 즉시 Fallback")
            print("⚠️ [PlannerAgent] 검색 쿼리 없음 - 즉시 Fallback", file=sys.stdout, flush=True)
            from ..nodes.writer import writer as writer_func
            updated_state = {**state, **result}
            updated_state = await writer_func(updated_state)
            from ..nodes.save_response import save_response as save_response_func
            updated_state = await save_response_func(updated_state)
            updated_state["writer_executed"] = True
            return updated_state
        
        # 쿼리 개수 기록
        if search_queries:
            query_count = len(search_queries)
            self.add_to_memory("last_query_count", query_count)
            
            # 평균 쿼리 개수 업데이트
            plan_count = self.get_state("plan_count", 1)
            avg_count = self.get_state("avg_query_count", 0.0)
            new_avg = (avg_count * (plan_count - 1) + query_count) / plan_count
            self.update_state(avg_query_count=new_avg)
            
            # ResearcherAgent에게 검색 계획 공유 (정보만 공유, 호출하지 않음)
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
        
        # Planner 함수의 결과만 반환 (LangGraph 그래프가 researcher → grader → writer 순서로 실행)
        updated_state = {**state, **result}
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
        """Grader 처리 로직 - LangGraph 그래프를 통해 실행됨"""
        import sys
        self.update_state(grade_count=self.get_state("grade_count", 0) + 1)
        
        # 기존 Grader 함수 호출만 수행 (LangGraph 그래프가 이후 흐름을 관리)
        result = await grader_func(state)
        
        # 점수 기록
        grader_score = result.get("grader_score", 0.0)
        is_sufficient = result.get("is_sufficient", False)
        
        self.add_to_memory("last_grader_score", grader_score)
        
        # 평균 점수 업데이트
        grade_count = self.get_state("grade_count", 1)
        avg_score = self.get_state("avg_score", 0.0)
        new_avg = (avg_score * (grade_count - 1) + grader_score) / grade_count
        self.update_state(avg_score=new_avg)
        
        # 충분한 결과 개수 업데이트
        if is_sufficient:
            self.update_state(sufficient_count=self.get_state("sufficient_count", 0) + 1)
        
        # Grader 함수의 결과만 반환 (LangGraph 그래프의 route_from_grader가 writer 또는 planner로 라우팅)
        updated_state = {**state, **result}
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
            if ai_messages and len(ai_messages) > 1:  # Coordinator(router) 응답 + 최종 응답
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
