"""
Coordinator Agent - 멀티 에이전트 협업 시스템
에이전트들의 순차적 협업을 관리하고 조율
"""
import logging
from typing import Optional
from .base_agent import BaseAgent
from ..models import ChatState, QuestionType
from .agent_registry import get_registry

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
        멀티 에이전트 협업 워크플로우
        
        역할:
        1. RouterAgent를 통해 질문 분류
        2. 적절한 첫 번째 에이전트에게 작업 위임
        3. 이후 각 에이전트가 정해진 순서대로 협업
        """
        import sys
        from langchain_core.messages import HumanMessage
        
        logger.info("="*60)
        logger.info("🚀 멀티 에이전트 협업 시스템 시작")
        logger.info("   - Coordinator가 초기 라우팅 수행")
        logger.info("   - 이후 에이전트들이 순차적으로 협업")
        print("="*60, file=sys.stdout, flush=True)
        print("🚀 멀티 에이전트 협업 시스템 시작", file=sys.stdout, flush=True)
        print("="*60, file=sys.stdout, flush=True)
        
        registry = get_registry()
        
        # Step 1: RouterAgent가 질문 분류 (초기 라우팅)
        router_agent = registry.get_agent("RouterAgent")
        if not router_agent:
            logger.error("❌ RouterAgent를 찾을 수 없습니다")
            return state
        
        logger.info("📋 Step 1: RouterAgent - 질문 분류")
        print("📋 Step 1: RouterAgent - 질문 분류", file=sys.stdout, flush=True)
        
        # 디버깅: 원본 state의 messages 확인
        original_messages = state.get("messages", [])
        logger.info(f"🔍 [Coordinator] RouterAgent 호출 전 messages: {len(original_messages)}개")
        
        state = await router_agent.process(state)
        
        # 디버깅: RouterAgent 실행 후 state의 messages 확인
        after_router_messages = state.get("messages", [])
        logger.info(f"🔍 [Coordinator] RouterAgent 호출 후 messages: {len(after_router_messages)}개")
        
        # Step 2: 첫 번째 에이전트에게 작업 위임 (이후는 자율)
        question_type = state.get("question_type")
        specialist_used = state.get("specialist_used")
        
        # 첫 번째 에이전트 결정
        first_agent_name = None
        if question_type == QuestionType.SIMPLE_CHAT or specialist_used == "simple_chat":
            first_agent_name = "SimpleChatAgent"
        elif question_type == QuestionType.FAQ or specialist_used == "faq" or question_type == QuestionType.GENERAL:
            first_agent_name = "FAQAgent"
        elif question_type == QuestionType.TRANSACTION or specialist_used == "transaction":
            first_agent_name = "TransactionAgent"
        elif question_type == QuestionType.WEB_SEARCH or specialist_used == "web_search" or question_type == QuestionType.HYBRID:
            first_agent_name = "PlannerAgent"
        
        if not first_agent_name:
            logger.warning("⚠️ 첫 번째 에이전트를 결정할 수 없습니다. FAQAgent로 기본 설정")
            first_agent_name = "FAQAgent"
        
        # Step 3: 첫 번째 에이전트에게 작업 위임
        logger.info(f"🎯 Step 2: {first_agent_name}에게 작업 위임")
        logger.info(f"   - 이후 {first_agent_name}이 정해진 워크플로우 실행")
        print(f"🎯 Step 2: {first_agent_name}에게 작업 위임", file=sys.stdout, flush=True)
        print(f"   (이후 정해진 순서대로 협업)", file=sys.stdout, flush=True)
        
        # 디버깅: FirstAgent 호출 전 state의 messages 확인
        before_first_agent_messages = state.get("messages", [])
        logger.info(f"🔍 [Coordinator] {first_agent_name} 호출 전 messages: {len(before_first_agent_messages)}개")
        if before_first_agent_messages:
            user_msgs = [msg for msg in before_first_agent_messages if isinstance(msg, HumanMessage)]
            logger.info(f"🔍 [Coordinator] 사용자 메시지: {len(user_msgs)}개")
            if user_msgs:
                logger.info(f"🔍 [Coordinator] 마지막 사용자 메시지: {user_msgs[-1].content[:50]}...")
        
        first_agent = registry.get_agent(first_agent_name)
        if first_agent:
            state = await first_agent.process(state)
        else:
            logger.error(f"❌ {first_agent_name}을 찾을 수 없습니다")
        
        logger.info("="*60)
        logger.info("✅ 멀티 에이전트 협업 워크플로우 완료")
        logger.info(f"   - 총 {len(registry.list_agents())}개 에이전트 등록")
        print("="*60, file=sys.stdout, flush=True)
        print("✅ 멀티 에이전트 협업 워크플로우 완료", file=sys.stdout, flush=True)
        print("="*60, file=sys.stdout, flush=True)
        
        return state


# 싱글톤 인스턴스
_coordinator_agent = None


def get_coordinator_agent() -> CoordinatorAgent:
    """Coordinator 에이전트 인스턴스 가져오기"""
    global _coordinator_agent
    if _coordinator_agent is None:
        _coordinator_agent = CoordinatorAgent()
    return _coordinator_agent
