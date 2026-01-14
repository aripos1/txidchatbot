"""
LangGraph를 사용한 챗봇 그래프 구현 (Router-Specialist 아키텍처)
분리된 노드들을 조합하여 그래프 구성

멀티 에이전트 모드:
- USE_TRUE_MULTI_AGENT=true: CoordinatorAgent가 모든 에이전트의 협업을 관리
- USE_TRUE_MULTI_AGENT=false: 그래프가 에이전트를 순차적으로 호출 (LangGraph 제어)
"""
import os
import logging
from typing import Literal
from langgraph.graph import StateGraph, END
from langsmith import traceable

from .models import ChatState, QuestionType
from .configuration import config
from .utils import ensure_logger_setup

# 노드 임포트
from .nodes import (
    router,
    intent_clarifier,
    simple_chat_specialist,
    faq_specialist,
    transaction_specialist,
    check_db,
    planner,
    researcher,
    summarizer,
    grader,
    writer,
    save_response,
)

logger = logging.getLogger(__name__)


# ========== 라우팅 분기 함수 ==========
def route_to_specialist(state: ChatState) -> Literal[
    "simple_chat", 
    "faq", 
    "transaction", 
    "web_search", 
    "hybrid",
    "general",
    "intent_clarifier"
]:
    """라우팅 결정에 따라 전문가로 분기"""
    question_type = state.get("question_type")
    specialist_used = state.get("specialist_used")
    needs_clarification = state.get("needs_clarification", False)
    
    # 의도 명확화가 필요한 경우
    if needs_clarification or question_type == QuestionType.INTENT_CLARIFICATION:
        return "intent_clarifier"
    
    if specialist_used:
        if specialist_used == "simple_chat":
            return "simple_chat"
        elif specialist_used == "transaction":
            return "transaction"
        elif specialist_used == "faq":
            return "faq"
        elif specialist_used == "web_search":
            return "web_search"
        elif specialist_used == "hybrid":
            return "web_search"  # hybrid는 web_search(planner)로 직접 라우팅
        elif specialist_used == "intent_clarifier":
            return "intent_clarifier"
    
    # question_type 기반 분기
    if question_type == QuestionType.SIMPLE_CHAT:
        return "simple_chat"
    elif question_type == QuestionType.TRANSACTION:
        return "transaction"
    elif question_type == QuestionType.FAQ:
        return "faq"
    elif question_type == QuestionType.WEB_SEARCH:
        return "web_search"
    elif question_type == QuestionType.HYBRID:
        return "web_search"  # hybrid는 web_search(planner)로 직접 라우팅
    elif question_type == QuestionType.INTENT_CLARIFICATION:
        return "intent_clarifier"
    else:
        return "general"


def route_from_faq(state: ChatState) -> Literal["planner", "save_response"]:
    """FAQ Specialist에서 Deep Research 필요 여부 확인"""
    needs_web_search = state.get("needs_web_search", False)
    question_type = state.get("question_type")
    
    if needs_web_search or question_type == QuestionType.HYBRID:
        return "planner"  # Deep Research로 직접 연결
    else:
        return "save_response"


def route_from_grader(state: ChatState) -> Literal["planner", "writer", "fallback"]:
    """Grader 평가 결과에 따라 라우팅"""
    is_sufficient = state.get("is_sufficient", False)
    search_loop_count = state.get("search_loop_count", 0)
    grader_score = state.get("grader_score", 0.0)
    
    # 3회 이상 재검색했으면 Fallback
    if search_loop_count >= 3:
        logger.warning(f"검색 반복 초과 ({search_loop_count}회) - Fallback")
        return "fallback"
    
    # 충분한 정보가 있으면 Writer로
    if is_sufficient and grader_score >= 0.7:
        logger.info(f"검색 결과 충분 (점수: {grader_score:.2f}) - Writer")
        return "writer"
    
    # 부족하면 재검색
    logger.info(f"검색 결과 부족 (점수: {grader_score:.2f}) - 재검색")
    return "planner"


@traceable(name="create_chatbot_graph", run_type="chain")
def create_chatbot_graph():
    """LangGraph를 사용한 챗봇 그래프 생성 (Router-Specialist 아키텍처 + 멀티 에이전트)"""
    
    # 설정 유효성 검사
    config.validate()
    ensure_logger_setup()
    
    # 멀티 에이전트 시스템 초기화 - 모든 에이전트를 레지스트리에 등록
    from .agents.agent_registry import get_registry
    from .agents import (
        get_router_agent,
        get_faq_agent,
        get_transaction_agent,
        get_simple_chat_agent,
        get_planner_agent,
        get_researcher_agent,
        get_grader_agent,
    )
    
    registry = get_registry()
    
    # 모든 에이전트 등록
    registry.register(get_router_agent())
    registry.register(get_faq_agent())
    registry.register(get_transaction_agent())
    registry.register(get_simple_chat_agent())
    registry.register(get_planner_agent())
    registry.register(get_researcher_agent())
    registry.register(get_grader_agent())
    
    logger.info(f"✅ 기본 에이전트 등록 완료: {len(registry.list_agents())}개")
    
    # 멀티 에이전트 협업 모드 활성화 여부 확인
    use_true_multi_agent = os.getenv("USE_TRUE_MULTI_AGENT", "false").lower() == "true"
    
    if use_true_multi_agent:
        # 협업 모드: CoordinatorAgent가 에이전트 간 협업을 관리
        from .agents.coordinator_agent import get_coordinator_agent
        coordinator_agent = get_coordinator_agent()
        registry.register(coordinator_agent)
        
        logger.info("🤝 멀티 에이전트 협업 모드 활성화: CoordinatorAgent가 에이전트 협업 관리")
        logger.info(f"✅ 시스템 초기화 완료: 총 {len(registry.list_agents())}개 에이전트")
        
        # 간단한 그래프: CoordinatorAgent만 실행
        workflow = StateGraph(ChatState)
        workflow.add_node("coordinator", coordinator_agent.process)
        workflow.set_entry_point("coordinator")
        workflow.add_edge("coordinator", END)
        
        app = workflow.compile()
        logger.info("✅ 멀티 에이전트 협업 그래프 생성 완료")
        return app
    
    # LangGraph 제어 모드: 그래프가 에이전트를 순차적으로 호출
    logger.info("📊 LangGraph 제어 모드: 그래프 엣지로 워크플로우 관리")
    
    # ========== 그래프 구성 ==========
    workflow = StateGraph(ChatState)
    
    # 노드 추가
    workflow.add_node("router", router)
    workflow.add_node("intent_clarifier", intent_clarifier)
    workflow.add_node("simple_chat_specialist", simple_chat_specialist)
    workflow.add_node("faq_specialist", faq_specialist)
    workflow.add_node("transaction_specialist", transaction_specialist)
    
    # Deep Research 노드들
    workflow.add_node("check_db", check_db)
    workflow.add_node("planner", planner)
    workflow.add_node("researcher", researcher)
    workflow.add_node("summarizer", summarizer)
    workflow.add_node("grader", grader)
    workflow.add_node("writer", writer)
    workflow.add_node("save_response", save_response)
    
    # 엔트리 포인트
    workflow.set_entry_point("router")
    
    # Router에서 전문가로 라우팅
    workflow.add_conditional_edges(
        "router",
        route_to_specialist,
        {
            "intent_clarifier": "intent_clarifier",
            "simple_chat": "simple_chat_specialist",
            "faq": "faq_specialist",
            "transaction": "transaction_specialist",
            "web_search": "planner",
            "hybrid": "planner",  # hybrid는 Deep Research로 직접 연결
            "general": "faq_specialist"
        }
    )
    
    # Intent Clarifier → Save
    workflow.add_edge("intent_clarifier", "save_response")
    
    # SimpleChat → Save
    workflow.add_edge("simple_chat_specialist", "save_response")
    
    # FAQ → Save 또는 Deep Research
    workflow.add_conditional_edges(
        "faq_specialist",
        route_from_faq,
        {
            "planner": "planner",  # Deep Research로 직접 연결
            "save_response": "save_response"
        }
    )
    
    # Transaction → Save
    workflow.add_edge("transaction_specialist", "save_response")
    
    # Deep Research 순환형 구조
    # Planner → Researcher
    workflow.add_edge("planner", "researcher")
    
    # Researcher → Grader
    workflow.add_edge("researcher", "grader")
    
    # Grader → Planner(재검색) 또는 Writer(답변)
    workflow.add_conditional_edges(
        "grader",
        route_from_grader,
        {
            "planner": "planner",
            "writer": "writer",
            "fallback": "writer"
        }
    )
    
    # Writer → Save
    workflow.add_edge("writer", "save_response")
    
    # Save → END
    workflow.add_edge("save_response", END)
    
    # 그래프 컴파일
    app = workflow.compile()
    
    logger.info("✅ 챗봇 그래프 생성 완료 (Router-Specialist 아키텍처)")
    
    return app


# 전역 그래프 인스턴스
_chatbot_graph = None


@traceable(name="get_chatbot_graph", run_type="chain")
def get_chatbot_graph():
    """챗봇 그래프 인스턴스 가져오기 (싱글톤 패턴)"""
    global _chatbot_graph
    try:
        if _chatbot_graph is None:
            _chatbot_graph = create_chatbot_graph()
        return _chatbot_graph
    except Exception as e:
        logger.error(f"챗봇 그래프 생성 실패: {e}")
        raise


# 하위 호환성을 위한 별칭
chatbot_graph = None  # 기존 코드와 호환


def initialize_graph():
    """그래프 초기화 (기존 코드 호환용)"""
    global chatbot_graph
    chatbot_graph = get_chatbot_graph()
    return chatbot_graph

