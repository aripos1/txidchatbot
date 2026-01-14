"""
에이전트 레지스트리 - 에이전트 간 직접 소통을 위한 중앙 레지스트리
멀티 에이전트 협업 시스템의 핵심
"""
import logging
from typing import Dict, Optional, List, Any
from .base_agent import BaseAgent
from ..models import ChatState

logger = logging.getLogger(__name__)


class AgentRegistry:
    """에이전트 레지스트리 - 모든 에이전트를 등록하고 관리"""
    
    _instance: Optional['AgentRegistry'] = None
    _agents: Dict[str, BaseAgent] = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def register(self, agent: BaseAgent):
        """에이전트 등록"""
        self._agents[agent.name] = agent
        logger.info(f"✅ 에이전트 등록: {agent.name}")
    
    def get_agent(self, agent_name: str) -> Optional[BaseAgent]:
        """에이전트 가져오기"""
        return self._agents.get(agent_name)
    
    def get_all_agents(self) -> Dict[str, BaseAgent]:
        """모든 에이전트 가져오기"""
        return self._agents.copy()
    
    def list_agents(self) -> List[str]:
        """등록된 에이전트 목록"""
        return list(self._agents.keys())
    
    async def send_message(self, from_agent: str, to_agent: str, message: Dict[str, Any], state: ChatState) -> ChatState:
        """에이전트 간 메시지 전송
        
        Args:
            from_agent: 메시지를 보내는 에이전트 이름
            to_agent: 메시지를 받는 에이전트 이름
            message: 메시지 내용
            state: 현재 상태
            
        Returns:
            업데이트된 상태
        """
        sender = self.get_agent(from_agent)
        receiver = self.get_agent(to_agent)
        
        if not sender:
            logger.warning(f"⚠️ 에이전트를 찾을 수 없음: {from_agent}")
            return state
        
        if not receiver:
            logger.warning(f"⚠️ 에이전트를 찾을 수 없음: {to_agent}")
            return state
        
        logger.info(f"📨 [{from_agent}] → [{to_agent}]: {message.get('type', 'message')}")
        
        # 상호작용 기록
        sender.record_interaction(to_agent, "send_message", message)
        receiver.record_interaction(from_agent, "receive_message", message)
        
        # 메시지 처리
        if message.get("type") == "request_help":
            # 도움 요청 - 다른 에이전트가 처리
            return await receiver.process(state)
        elif message.get("type") == "delegate":
            # 작업 위임
            return await receiver.process(state)
        elif message.get("type") == "share_info":
            # 정보 공유
            receiver.add_to_memory(f"shared_from_{from_agent}", message.get("data"))
            return state
        else:
            # 일반 메시지
            return await receiver.process(state)
    
    async def collaborate(self, agents: List[str], state: ChatState, task: str) -> ChatState:
        """여러 에이전트가 협업하여 작업 수행
        
        Args:
            agents: 협업할 에이전트 목록
            state: 현재 상태
            task: 수행할 작업 설명
            
        Returns:
            업데이트된 상태
        """
        logger.info(f"🤝 에이전트 협업 시작: {', '.join(agents)} - 작업: {task}")
        
        current_state = state
        
        for agent_name in agents:
            agent = self.get_agent(agent_name)
            if agent:
                logger.info(f"  → [{agent_name}] 처리 중...")
                current_state = await agent.process(current_state)
            else:
                logger.warning(f"  ⚠️ 에이전트를 찾을 수 없음: {agent_name}")
        
        logger.info(f"✅ 에이전트 협업 완료")
        return current_state


# 전역 레지스트리 인스턴스
_registry = None


def get_registry() -> AgentRegistry:
    """에이전트 레지스트리 인스턴스 가져오기"""
    global _registry
    if _registry is None:
        _registry = AgentRegistry()
    return _registry
