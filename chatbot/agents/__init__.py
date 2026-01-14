"""
에이전트 모듈 - 멀티 에이전트 아키텍처

각 Specialist와 Router는 독립적인 Agent로 구현되어 있습니다.
기존 노드 함수들은 Agent를 래핑하여 호출하므로 호환성이 유지됩니다.

멀티 에이전트 협업 기능:
- 에이전트 간 직접 메시지 전송
- 에이전트 간 작업 위임
- 에이전트 간 정보 공유
- 여러 에이전트 협업
"""
from .base_agent import BaseAgent
from .agent_registry import AgentRegistry, get_registry
from .router_agent import RouterAgent, get_router_agent
from .specialist_agents import (
    FAQAgent,
    TransactionAgent,
    SimpleChatAgent,
    get_faq_agent,
    get_transaction_agent,
    get_simple_chat_agent,
)
from .research_agent import ResearchAgent, get_research_agent
from .deep_research_agents import (
    PlannerAgent,
    ResearcherAgent,
    GraderAgent,
    get_planner_agent,
    get_researcher_agent,
    get_grader_agent,
)

__all__ = [
    # Base
    "BaseAgent",
    "AgentRegistry",
    "get_registry",
    # Agents
    "RouterAgent",
    "FAQAgent",
    "TransactionAgent",
    "SimpleChatAgent",
    "ResearchAgent",
    "PlannerAgent",
    "ResearcherAgent",
    "GraderAgent",
    # Factory functions
    "get_router_agent",
    "get_faq_agent",
    "get_transaction_agent",
    "get_simple_chat_agent",
    "get_research_agent",
    "get_planner_agent",
    "get_researcher_agent",
    "get_grader_agent",
]
