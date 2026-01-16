"""
Coordinator Agent - 멀티 에이전트 협업 시스템
LangGraph 그래프를 통해 실행되는 래퍼 노드
"""
import logging
from .base_agent import BaseAgent
from ..models import ChatState

logger = logging.getLogger(__name__)


class CoordinatorAgent(BaseAgent):
    """
    Coordinator Agent - 멀티 에이전트 협업 관리
    
    역할:
    1. 초기 RouterAgent 호출 (질문 분류)
    2. 첫 번째 Specialist Agent에게 작업 위임
    3. 이후는 각 에이전트가 정해진 순서대로 다음 에이전트 호출
    """
    
    def __init__(self):
        super().__init__(
            name="CoordinatorAgent",
            description="멀티 에이전트 협업을 관리하는 코디네이터"
        )
    
    async def process(self, state: ChatState) -> ChatState:
        """
        Coordinator 노드 - LangGraph 그래프를 통해 실행되는 래퍼
        
        역할:
        1. 멀티 에이전트 시스템 초기화 로그만 출력
        2. 실제 로직은 router 노드에서 처리
        3. 이후 흐름은 LangGraph의 조건부 엣지로 처리됨 (SSE 지원)
        
        주의: 이 함수는 LangGraph 노드로 실행되므로, 
        내부에서 다른 에이전트를 직접 호출하지 않음.
        대신 LangGraph 그래프의 조건부 엣지를 통해 다음 노드가 선택됨.
        """
        import sys
        
        logger.info("="*60)
        logger.info("🚀 멀티 에이전트 협업 시스템 시작")
        logger.info("   - Coordinator가 초기화 로그 출력")
        logger.info("   - 이후 LangGraph 그래프를 통해 실행됨 (SSE 지원)")
        print("="*60, file=sys.stdout, flush=True)
        print("🚀 멀티 에이전트 협업 시스템 시작", file=sys.stdout, flush=True)
        print("="*60, file=sys.stdout, flush=True)
        
        # Coordinator는 단순히 초기화 로그만 출력
        # 실제 라우팅은 router 노드에서 처리되고,
        # 이후 흐름은 LangGraph 그래프의 조건부 엣지로 처리됨
        # 이렇게 하면 모든 실행 단계가 LangGraph 노드로 실행되어 SSE가 동작함
        
        # state를 그대로 반환 (변경 없음)
        # 실제 라우팅은 router 노드에서 처리됨
        return state


# 싱글톤 인스턴스
_coordinator_agent = None


def get_coordinator_agent() -> CoordinatorAgent:
    """Coordinator 에이전트 인스턴스 가져오기"""
    global _coordinator_agent
    if _coordinator_agent is None:
        _coordinator_agent = CoordinatorAgent()
    return _coordinator_agent
