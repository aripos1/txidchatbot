"""
Research Agent - Deep Research 워크플로우를 관리하는 에이전트
Planner, Researcher, Grader, Writer를 조율하는 메인 에이전트
"""
import logging
from typing import List
from .base_agent import BaseAgent
from ..models import ChatState, QuestionType
from ..nodes.deep_research import (
    planner as planner_func,
    researcher as researcher_func,
    grader as grader_func,
)
from ..nodes.writer import writer as writer_func

logger = logging.getLogger(__name__)


class ResearchAgent(BaseAgent):
    """Research Agent - 웹 검색 및 Deep Research 워크플로우 관리"""
    
    def __init__(self):
        super().__init__(
            name="ResearchAgent",
            description="웹 검색, 시세 조회, Deep Research 워크플로우를 관리하는 전문가 에이전트"
        )
        self.update_state(
            research_count=0,
            search_loop_count=0,
            avg_grader_score=0.0,
            success_count=0
        )
    
    async def process(self, state: ChatState) -> ChatState:
        """Research 워크플로우 처리"""
        self.update_state(research_count=self.get_state("research_count", 0) + 1)
        
        # Planner 단계
        logger.info(f"[{self.name}] Planner 단계 시작")
        planner_result = await planner_func(state)
        state = {**state, **planner_result}
        
        # Researcher 단계
        logger.info(f"[{self.name}] Researcher 단계 시작")
        researcher_result = await researcher_func(state)
        state = {**state, **researcher_result}
        
        # Grader 단계
        logger.info(f"[{self.name}] Grader 단계 시작")
        grader_result = await grader_func(state)
        state = {**state, **grader_result}
        
        # Grader 점수 기록
        grader_score = grader_result.get("grader_score", 0.0)
        self.add_to_memory("last_grader_score", grader_score)
        
        # 평균 점수 업데이트
        research_count = self.get_state("research_count", 1)
        avg_score = self.get_state("avg_grader_score", 0.0)
        new_avg = (avg_score * (research_count - 1) + grader_score) / research_count
        self.update_state(avg_grader_score=new_avg)
        
        # 검색 루프 카운트 업데이트
        search_loop_count = state.get("search_loop_count", 0)
        self.update_state(search_loop_count=search_loop_count)
        
        # Writer 단계 (충분한 경우)
        is_sufficient = grader_result.get("is_sufficient", False)
        if is_sufficient or search_loop_count >= 3:
            logger.info(f"[{self.name}] Writer 단계 시작 (충분: {is_sufficient}, 루프: {search_loop_count})")
            writer_result = await writer_func(state)
            state = {**state, **writer_result}
            
            # 성공률 업데이트
            if is_sufficient:
                success_count = self.get_state("success_count", 0)
                self.update_state(success_count=success_count + 1)
        
        return state
    
    def can_handle(self, state: ChatState) -> bool:
        """웹 검색 또는 Hybrid 질문인지 확인"""
        question_type = state.get("question_type")
        specialist_used = state.get("specialist_used")
        needs_web_search = state.get("needs_web_search", False)
        return (
            question_type == QuestionType.WEB_SEARCH or
            question_type == QuestionType.HYBRID or
            specialist_used == "web_search" or
            needs_web_search
        )
    
    def get_capabilities(self) -> List[str]:
        return [
            "웹 검색 계획 수립",
            "Google/DuckDuckGo 검색",
            "시세 API 조회",
            "검색 결과 평가",
            "답변 작성",
            "재검색 루프 관리"
        ]


# 에이전트 인스턴스 생성 (싱글톤 패턴)
_research_agent = None


def get_research_agent() -> ResearchAgent:
    """Research 에이전트 인스턴스 가져오기"""
    global _research_agent
    if _research_agent is None:
        _research_agent = ResearchAgent()
    return _research_agent


# 기존 코드 호환성을 위한 래퍼 함수
# 주의: ResearchAgent는 여러 단계를 포함하므로, 
# 기존 그래프 구조에서는 각 단계가 별도 노드로 호출됩니다.
# 따라서 이 래퍼는 사용하지 않고, 각 단계를 개별적으로 호출합니다.
