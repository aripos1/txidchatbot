"""
LangGraph를 사용한 챗봇 그래프 구현 (Coordinator-Specialist 아키텍처)
분리된 노드들을 조합하여 그래프 구성

CoordinatorAgent가 라우팅을 직접 처리하고, 모든 에이전트가 LangGraph 노드로 등록되어 순차적으로 실행됩니다.
"""
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


def route_from_planner(state: ChatState) -> Literal["save_response", "researcher"]:
    """Planner에서 Writer가 이미 실행되었는지 확인 (Fallback 케이스만)"""
    # PlannerAgent가 Fallback 케이스에서 Writer를 실행한 경우 (쿼리 없음, 상태 손상 등)
    writer_executed = state.get("writer_executed", False)
    if writer_executed:
        logger.info("PlannerAgent가 Fallback에서 Writer를 실행함 (writer_executed 플래그) - save_response로 이동")
        return "save_response"
    
    # 정상 흐름: researcher로 진행 (LangGraph 그래프가 planner → researcher → grader → writer 순서로 실행)
    return "researcher"


def route_from_grader(state: ChatState) -> Literal["planner", "writer", "fallback", "save_response"]:
    """Grader 평가 결과에 따라 라우팅"""
    from langchain_core.messages import AIMessage
    
    # 이미 Writer가 실행되었는지 확인 (멀티 에이전트 모드에서 GraderAgent가 직접 호출한 경우)
    # 플래그 확인 (가장 확실한 방법)
    writer_executed = state.get("writer_executed", False)
    if writer_executed:
        logger.info("이미 Writer가 실행됨 (writer_executed 플래그) - save_response로 직접 이동하여 종료")
        return "save_response"  # writer를 건너뛰고 바로 save_response로
    
    # messages에서 최종 응답 확인
    messages = state.get("messages", [])
    if messages:
        ai_messages = [msg for msg in messages if isinstance(msg, AIMessage)]
        if len(ai_messages) >= 2:  # Router 응답 + Writer 응답
            last_ai_msg = ai_messages[-1]
            if hasattr(last_ai_msg, "content"):
                content = str(last_ai_msg.content)
                # 실제 응답은 일반적으로 100자 이상이고, "[웹 검색 완료]" 같은 상태 메시지가 아님
                if len(content) > 100 and "[웹 검색 완료]" not in content:
                    # 상태 메시지가 아니고, 실제 답변 내용이 있는지 확인
                    is_status_message = any(keyword in content for keyword in [
                        "[웹 검색 완료]", "[검색 결과]", "검색 중", "처리 중"
                    ])
                    if not is_status_message:
                        # 실제 이벤트나 정보가 포함되어 있으면 Writer가 실행된 것으로 간주
                        has_actual_content = any(keyword in content.lower() for keyword in [
                            "이벤트", "프로모션", "진행", "안내", "정보", "빗썸", "bithumb",
                            "주년", "혜택", "참여", "할인", "경품"
                        ])
                        if has_actual_content:
                            logger.info(f"이미 Writer가 실행됨 (최종 응답 감지: {len(content)}자) - 더 이상 진행하지 않음")
                            return "fallback"
    
    is_sufficient = state.get("is_sufficient", False)
    search_loop_count = state.get("search_loop_count", 0)
    grader_score = state.get("grader_score")
    
    # grader_score가 None이거나 숫자가 아닌 경우 기본값 사용
    if grader_score is None:
        grader_score = 0.0
    try:
        grader_score = float(grader_score)
    except (TypeError, ValueError):
        grader_score = 0.0
    
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
        get_faq_agent,
        get_transaction_agent,
        get_simple_chat_agent,
        get_planner_agent,
        get_researcher_agent,
        get_grader_agent,
    )
    
    registry = get_registry()
    
    # 모든 에이전트 등록 (RouterAgent 제거 - nodes/router.py의 router 함수 직접 사용)
    registry.register(get_faq_agent())
    registry.register(get_transaction_agent())
    registry.register(get_simple_chat_agent())
    registry.register(get_planner_agent())
    registry.register(get_researcher_agent())
    registry.register(get_grader_agent())
    
    logger.info(f"✅ 기본 에이전트 등록 완료: {len(registry.list_agents())}개")
    
    # CoordinatorAgent가 라우팅을 직접 처리하는 멀티 에이전트 협업 모드
    # LangGraph SSE 지원을 위해 모든 실행 단계를 LangGraph 노드로 실행
    from .agents.coordinator_agent import get_coordinator_agent
    coordinator_agent = get_coordinator_agent()
    registry.register(coordinator_agent)
    
    logger.info("🤝 멀티 에이전트 협업 모드: CoordinatorAgent가 라우팅을 직접 처리")
    logger.info("   - 모든 노드가 LangGraph 노드로 등록됨 (SSE 지원)")
    logger.info(f"✅ 시스템 초기화 완료: 총 {len(registry.list_agents())}개 에이전트")
    
    # LangGraph SSE를 위해 모든 노드를 등록하고 조건부 엣지로 연결
    workflow = StateGraph(ChatState)
    
    # 모든 노드 등록 (LangGraph SSE 지원)
    workflow.add_node("coordinator", coordinator_agent.process)
    # router 노드는 제거 - CoordinatorAgent가 직접 라우팅 처리
    workflow.add_node("intent_clarifier", intent_clarifier)
    workflow.add_node("simple_chat_specialist", simple_chat_specialist)
    workflow.add_node("faq_specialist", faq_specialist)
    workflow.add_node("transaction_specialist", transaction_specialist)
    workflow.add_node("check_db", check_db)
    workflow.add_node("planner", planner)
    workflow.add_node("researcher", researcher)
    workflow.add_node("summarizer", summarizer)
    workflow.add_node("grader", grader)
    workflow.add_node("writer", writer)
    workflow.add_node("save_response", save_response)
    
    # 엔트리 포인트: coordinator (라우팅 포함)
    workflow.set_entry_point("coordinator")
    
    # Coordinator에서 직접 전문가로 라우팅 (조건부 엣지)
    # CoordinatorAgent가 router 로직을 직접 실행하므로 router 노드 없이 바로 라우팅
    workflow.add_conditional_edges(
        "coordinator",
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
    
    # FAQ → Save 또는 Deep Research (조건부 엣지)
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
    # Planner → Save (writer_executed 플래그가 있으면) 또는 Researcher (없으면)
    workflow.add_conditional_edges(
        "planner",
        route_from_planner,
        {
            "save_response": "save_response",
            "researcher": "researcher"
        }
    )
    
    # Researcher → Grader
    workflow.add_edge("researcher", "grader")
    
    # Grader → Planner(재검색) 또는 Writer(답변) 또는 Save(이미 실행됨) (조건부 엣지)
    workflow.add_conditional_edges(
        "grader",
        route_from_grader,
        {
            "planner": "planner",
            "writer": "writer",
            "fallback": "writer",
            "save_response": "save_response"  # writer_executed 플래그가 있으면 바로 save_response로
        }
    )
    
    # Writer → Save
    workflow.add_edge("writer", "save_response")
    
    # Save → END
    workflow.add_edge("save_response", END)
    
    app = workflow.compile()
    logger.info("✅ 멀티 에이전트 협업 그래프 생성 완료 (모든 노드 LangGraph 노드로 실행 - SSE 지원)")
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

