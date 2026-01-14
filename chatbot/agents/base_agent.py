"""
Base Agent 클래스 - 모든 에이전트의 기본 클래스
멀티 에이전트 아키텍처의 핵심
"""
import logging
from typing import Optional, Dict, Any, List
from abc import ABC, abstractmethod
from langchain_core.messages import BaseMessage
from langsmith import traceable
import asyncio

from ..models import ChatState

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """모든 에이전트의 기본 클래스
    
    각 에이전트는:
    1. 자신의 상태와 메모리를 관리
    2. 독립적으로 작업 수행
    3. 다른 에이전트와 협업 가능
    """
    
    def __init__(self, name: str, description: str = ""):
        """에이전트 초기화
        
        Args:
            name: 에이전트 이름
            description: 에이전트 설명
        """
        self.name = name
        self.description = description
        self.memory: List[Dict[str, Any]] = []  # 에이전트 메모리
        self.state: Dict[str, Any] = {}  # 에이전트 상태
        self.interaction_history: List[Dict[str, Any]] = []  # 다른 에이전트와의 상호작용 기록
        
    def add_to_memory(self, key: str, value: Any):
        """메모리에 정보 추가"""
        self.memory.append({"key": key, "value": value, "timestamp": self._get_timestamp()})
        logger.debug(f"[{self.name}] 메모리 추가: {key}")
    
    def get_from_memory(self, key: str) -> Optional[Any]:
        """메모리에서 정보 조회"""
        for item in reversed(self.memory):
            if item.get("key") == key:
                return item.get("value")
        return None
    
    def update_state(self, **kwargs):
        """에이전트 상태 업데이트"""
        self.state.update(kwargs)
        logger.debug(f"[{self.name}] 상태 업데이트: {list(kwargs.keys())}")
    
    def get_state(self, key: str, default: Any = None) -> Any:
        """에이전트 상태 조회"""
        return self.state.get(key, default)
    
    def record_interaction(self, other_agent: str, interaction_type: str, data: Dict[str, Any]):
        """다른 에이전트와의 상호작용 기록"""
        self.interaction_history.append({
            "other_agent": other_agent,
            "type": interaction_type,
            "data": data,
            "timestamp": self._get_timestamp()
        })
        logger.debug(f"[{self.name}] {other_agent}와 상호작용 기록: {interaction_type}")
    
    def _get_timestamp(self) -> str:
        """타임스탬프 생성"""
        from datetime import datetime
        return datetime.now().isoformat()
    
    @abstractmethod
    async def process(self, state: ChatState) -> ChatState:
        """에이전트의 주요 처리 로직 (하위 클래스에서 구현)
        
        Args:
            state: 현재 챗봇 상태
            
        Returns:
            업데이트된 상태
        """
        pass
    
    async def __call__(self, state: ChatState) -> ChatState:
        """에이전트를 함수처럼 호출 가능하도록 함 (기존 코드 호환성)"""
        import sys
        print(f"[{self.name}] 에이전트 실행 시작", file=sys.stdout, flush=True)
        logger.info(f"[{self.name}] 에이전트 실행 시작")
        try:
            result = await self.process(state)
            print(f"[{self.name}] 에이전트 실행 완료", file=sys.stdout, flush=True)
            logger.info(f"[{self.name}] 에이전트 실행 완료")
            return result
        except Exception as e:
            logger.error(f"[{self.name}] 에이전트 실행 실패: {e}", exc_info=True)
            raise
    
    def can_handle(self, state: ChatState) -> bool:
        """이 에이전트가 현재 상태를 처리할 수 있는지 확인
        
        Args:
            state: 현재 챗봇 상태
            
        Returns:
            처리 가능 여부
        """
        return True  # 기본적으로 항상 처리 가능
    
    def is_task_complete(self, state: ChatState) -> bool:
        """작업 완료 여부를 자율적으로 판단
        
        Args:
            state: 현재 챗봇 상태
            
        Returns:
            True: 작업 완료, 다른 에이전트 호출 불필요
            False: 추가 작업 필요, 다른 에이전트에게 위임
        """
        # 기본적으로는 응답이 있으면 완료로 판단
        messages = state.get("messages", [])
        if messages:
            from langchain_core.messages import AIMessage
            ai_messages = [msg for msg in messages if isinstance(msg, AIMessage)]
            if ai_messages:
                return True
        return False
    
    def get_capabilities(self) -> List[str]:
        """에이전트의 능력 목록 반환"""
        return []
    
    def reset(self):
        """에이전트 상태 초기화 (새 세션 시작 시)"""
        self.memory.clear()
        self.state.clear()
        self.interaction_history.clear()
        logger.debug(f"[{self.name}] 상태 초기화")
    
    async def request_help(self, other_agent_name: str, message: Dict[str, Any], state: ChatState) -> ChatState:
        """다른 에이전트에게 도움 요청
        
        Args:
            other_agent_name: 도움을 요청할 에이전트 이름
            message: 요청 메시지
            state: 현재 상태
            
        Returns:
            업데이트된 상태
        """
        from .agent_registry import get_registry
        registry = get_registry()
        
        return await registry.send_message(
            self.name,
            other_agent_name,
            {"type": "request_help", "data": message},
            state
        )
    
    async def delegate(self, other_agent_name: str, reason: str, state: ChatState) -> ChatState:
        """다른 에이전트에게 작업 위임
        
        Args:
            other_agent_name: 위임할 에이전트 이름
            reason: 위임 이유
            state: 현재 상태
            
        Returns:
            업데이트된 상태
        """
        from .agent_registry import get_registry
        registry = get_registry()
        
        logger.info(f"[{self.name}] → [{other_agent_name}] 작업 위임: {reason}")
        
        return await registry.send_message(
            self.name,
            other_agent_name,
            {"type": "delegate", "reason": reason},
            state
        )
    
    async def share_info(self, other_agent_name: str, data: Dict[str, Any], state: ChatState) -> ChatState:
        """다른 에이전트에게 정보 공유
        
        Args:
            other_agent_name: 정보를 공유할 에이전트 이름
            data: 공유할 데이터
            state: 현재 상태
            
        Returns:
            업데이트된 상태
        """
        from .agent_registry import get_registry
        registry = get_registry()
        
        return await registry.send_message(
            self.name,
            other_agent_name,
            {"type": "share_info", "data": data},
            state
        )
    
    async def call_agent(self, other_agent_name: str, state: ChatState) -> ChatState:
        """다른 에이전트를 직접 호출 (멀티 에이전트 협업)
        
        Args:
            other_agent_name: 호출할 에이전트 이름
            state: 현재 상태
            
        Returns:
            업데이트된 상태
        """
        from .agent_registry import get_registry
        import sys
        registry = get_registry()
        
        other_agent = registry.get_agent(other_agent_name)
        if not other_agent:
            logger.warning(f"⚠️ [{self.name}] 에이전트를 찾을 수 없음: {other_agent_name}")
            return state
        
        logger.info(f"📞 [{self.name}] → [{other_agent_name}] 직접 호출")
        print(f"📞 [{self.name}] → [{other_agent_name}] 직접 호출", file=sys.stdout, flush=True)
        
        # 상호작용 기록
        self.record_interaction(other_agent_name, "call_agent", {"state_keys": list(state.keys())})
        
        # 에이전트 직접 호출
        result = await other_agent.process(state)
        
        # 상태 병합
        updated_state = {**state, **result}
        
        logger.info(f"✅ [{self.name}] ← [{other_agent_name}] 호출 완료")
        print(f"✅ [{self.name}] ← [{other_agent_name}] 호출 완료", file=sys.stdout, flush=True)
        
        return updated_state
    
    async def call_agents_parallel(self, agent_names: List[str], state: ChatState) -> ChatState:
        """여러 에이전트를 병렬로 호출 (병렬 멀티 에이전트)
        
        Args:
            agent_names: 호출할 에이전트 이름 목록
            state: 현재 상태
            
        Returns:
            업데이트된 상태 (모든 에이전트 결과 병합)
        """
        from .agent_registry import get_registry
        import sys
        registry = get_registry()
        
        logger.info(f"🔀 [{self.name}] → 병렬 호출 시작: {', '.join(agent_names)}")
        print(f"🔀 [{self.name}] → 병렬 호출 시작: {', '.join(agent_names)}", file=sys.stdout, flush=True)
        
        # 모든 에이전트를 병렬로 호출
        tasks = []
        valid_agents = []
        
        for agent_name in agent_names:
            agent = registry.get_agent(agent_name)
            if agent:
                tasks.append(agent.process(state))
                valid_agents.append(agent_name)
                self.record_interaction(agent_name, "call_agent_parallel", {"state_keys": list(state.keys())})
            else:
                logger.warning(f"⚠️ [{self.name}] 에이전트를 찾을 수 없음: {agent_name}")
        
        if not tasks:
            logger.warning(f"⚠️ [{self.name}] 호출할 유효한 에이전트가 없습니다")
            return state
        
        # 병렬 실행
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 결과 병합
        updated_state = {**state}
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"⚠️ [{self.name}] {valid_agents[i]} 호출 실패: {result}")
                continue
            
            # 상태 병합
            updated_state = {**updated_state, **result}
        
        logger.info(f"✅ [{self.name}] ← 병렬 호출 완료: {len(valid_agents)}개 에이전트")
        print(f"✅ [{self.name}] ← 병렬 호출 완료: {len(valid_agents)}개 에이전트", file=sys.stdout, flush=True)
        
        return updated_state
