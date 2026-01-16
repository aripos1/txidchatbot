"""
Coordinator Agent - 멀티 에이전트 협업 시스템
Router 로직을 직접 실행하여 라우팅을 처리
"""
import logging
import sys
from .base_agent import BaseAgent
from ..models import ChatState
from ..nodes.router import router

logger = logging.getLogger(__name__)


class CoordinatorAgent(BaseAgent):
    """
    Coordinator Agent - 멀티 에이전트 협업 관리
    
    역할:
    1. 질문 분류 및 라우팅 결정 (Router 로직 직접 실행)
    2. 적절한 Specialist Agent로 라우팅
    3. 이후 흐름은 LangGraph의 조건부 엣지로 처리됨 (SSE 지원)
    """
    
    def __init__(self):
        super().__init__(
            name="CoordinatorAgent",
            description="멀티 에이전트 협업을 관리하는 코디네이터 (라우팅 포함)"
        )
    
    async def process(self, state: ChatState) -> ChatState:
        """
        Coordinator 노드 - Router 로직을 직접 실행하여 라우팅 처리
        
        역할:
        1. 멀티 에이전트 시스템 초기화 로그 출력
        2. Router 로직을 직접 실행하여 질문 분류 및 라우팅 결정
        3. 이후 흐름은 LangGraph의 조건부 엣지로 처리됨 (SSE 지원)
        """
        logger.info("="*60)
        logger.info("🚀 멀티 에이전트 협업 시스템 시작")
        logger.info("   - Coordinator가 라우팅을 직접 처리")
        logger.info("   - 이후 LangGraph 그래프를 통해 실행됨 (SSE 지원)")
        print("="*60, file=sys.stdout, flush=True)
        print("🚀 멀티 에이전트 협업 시스템 시작", file=sys.stdout, flush=True)
        print("   - Coordinator가 라우팅을 직접 처리", file=sys.stdout, flush=True)
        print("="*60, file=sys.stdout, flush=True)
        
        # Router 로직을 직접 실행하여 라우팅 결정
        router_result = await router(state)
        
        # router 결과를 state에 병합
        updated_state = {**state, **router_result}
        
        return updated_state


# 싱글톤 인스턴스
_coordinator_agent = None


def get_coordinator_agent() -> CoordinatorAgent:
    """Coordinator 에이전트 인스턴스 가져오기"""
    global _coordinator_agent
    if _coordinator_agent is None:
        _coordinator_agent = CoordinatorAgent()
    return _coordinator_agent
