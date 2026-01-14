"""
LangGraph 노드 모듈
각 노드는 ChatState를 입력받아 부분 상태를 반환

멀티 에이전트 아키텍처:
- 각 노드 함수는 해당 Agent를 래핑하여 호출
- 기존 코드 호환성 유지
"""
# 타입 import
from ..models import ChatState

# 에이전트 기반 노드 (멀티 에이전트 구조)
from ..agents.router_agent import router
from ..agents.specialist_agents import (
    simple_chat_specialist,
    faq_specialist,
    transaction_specialist,
)

# 기존 노드 함수들 (Agent로 래핑되지 않은 노드들)
from .intent_clarifier import intent_clarifier
from .writer import writer
from .save_response import save_response

# Deep Research 노드들 (Agent 래핑)
from .deep_research import (
    check_db,
    summarizer,
)

# Deep Research 노드들을 Agent로 래핑
from ..agents.deep_research_agents import (
    get_planner_agent,
    get_researcher_agent,
    get_grader_agent,
)

# Agent 래퍼 함수들
async def planner(state: ChatState) -> ChatState:
    """Planner 노드 - PlannerAgent를 통해 실행"""
    agent = get_planner_agent()
    return await agent(state)

async def researcher(state: ChatState) -> ChatState:
    """Researcher 노드 - ResearcherAgent를 통해 실행"""
    agent = get_researcher_agent()
    return await agent(state)

async def grader(state: ChatState) -> ChatState:
    """Grader 노드 - GraderAgent를 통해 실행"""
    agent = get_grader_agent()
    return await agent(state)

# Router의 RuleBasedClassifier는 직접 export
from .router import RuleBasedClassifier

__all__ = [
    # Core nodes (Agent 기반)
    "router",
    "RuleBasedClassifier",
    "intent_clarifier",
    "writer",
    "save_response",
    # Specialists (Agent 기반)
    "simple_chat_specialist",
    "faq_specialist",
    "transaction_specialist",
    # Deep Research (기존 구조 유지)
    "check_db",
    "planner",
    "researcher",
    "summarizer",
    "grader",
]

